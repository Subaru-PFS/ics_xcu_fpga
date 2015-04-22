
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

-- This entity is the "waveform processor unit" for CCD control lines.
-- It reads 32 bit "opcodes" from blockram, interprets them as a waveform
-- description, and drives 16 digital outputs accordingly.
--
-- 32 bit opcode format:
-- bits 31:16 = waveform values
-- bit 15 = CRC control
-- bits 14:0 = opcode duration
--
-- When an opcode is executed, its waveform values are driven on the outputs
-- and then the opcode duration passes before the next opcode is executed.
-- Duration is expressed in 40ns increments.  The maximum duration is
-- therefore around 1.3ms.  If a duration of several ms is required, it is
-- permissible to implement this with several consective opcodes that have
-- identical waveform values.
--
-- The CRC control bit is pulsed to inform the input chain that a row is over
-- and a CRC should be stored.
--
-- 15 of the 16 waveform values drive outputs directly.  Bit 13, (opcode bit
-- 29) is different.  A rising edge on this bit triggers SCK activity.
-- Output 13 is used for ADC SCK and must always pulse in bursts of 65.
--
-- The "len" and "reps" inputs are driven by the register file.  After "len"
-- opcodes, the waveform is over and the "instruction pointer" rolls over to
-- zero.  This loop occurs "reps" times, after which time the WPU stalls in a
-- finished state.
--
-- If adc_18bit_i is 1, we send 73 clock pulses, targeting the AD7690.  If
-- it is 0, we send 65 pulses, targeting the AD7686.
--
-- This logic is all clocked by the synch_in clock.  To synchronize multiple
-- units, software should take the following steps:
-- 1. Load waveform file into blockram and set LEN and REPS. (all units)
-- 2. assert WPU reset (all units)
-- 3. turn on clock (master)
-- 4. turn off clock (master)
-- 5. release WPU reset (all units)
-- 6. turn on clock (master)
--
-- It is step 6 that causes the complete synchronization.

entity ccd_wpu is
  port (
    -- clock and reset
    synch_i             : in  std_logic;
    clk_200mhz_i        : in  std_logic;
    rstn_i              : in  std_logic;
    
    -- SRAM interface
    sram_adr_o          : out std_logic_vector (17 downto 0);
    sram_dat_i          : in  std_logic_vector (31 downto 0);
    
    -- control signals to and from register block
    wpu_rst_i           : in  std_logic;
    adc_18bit_i         : in  std_logic;
    start_i             : in  std_logic_vector (15 downto 0);
    stop_i              : in  std_logic_vector (15 downto 0);
    reps_i              : in  std_logic_vector (31 downto 0);
    reps_o              : out std_logic_vector (31 downto 0);
    
    -- waveform output
    waveform_o          : out std_logic_vector (15 downto 0);

    -- active_o indicates that ADC SCK is active
    active_o            : out std_logic;
    crcctl_o            : out std_logic
  );
end ccd_wpu;

architecture rtl of ccd_wpu is

  -- signals
  signal main_timer     : unsigned (15 downto 0);
  signal duration       : unsigned (15 downto 0);
  signal sck_timer      : unsigned (11 downto 0);
  signal sck            : std_logic;
  signal scken_fifo     : std_logic_vector (7 downto 0);
  signal waveform       : std_logic_vector (15 downto 0);
  signal sram_adr       : unsigned (15 downto 0);
  signal reps           : unsigned (31 downto 0);
  signal finished       : boolean;
  signal adc_18bit_q    : std_logic;

begin
  -- output ports
  sram_adr_o <= STD_LOGIC_VECTOR(sram_adr) & "00";
  waveform_o(13) <= sck; -- SCK gets special treatment
  waveform_o(15 downto 14) <= waveform(15 downto 14);
  waveform_o(12 downto 0) <= waveform(12 downto 0);
  reps_o <= STD_LOGIC_VECTOR(reps);

  -- This 200MHz process exists only to generate the ADC SCK signal.  For the
  -- ADC, the requirement is that SCK is mostly idle, and then when we
  -- trigger it, we get 65 50MHz pulses.  The trigger is a positive transition
  -- on waveform(13).
  process(clk_200mhz_i, rstn_i)
  begin
    if rising_edge(clk_200mhz_i) then
      if (rstn_i = '0') then
        sck <= '1';
        sck_timer <= x"000";
        scken_fifo <= x"00";
        active_o <= '0';
        adc_18bit_q <= '0';
      else
        -- this is a clock domain crossing but there is no need to be careful
        -- because adc_18bit_i should not be changing during a readout.
        adc_18bit_q <= adc_18bit_i;
        -- SCK needs to idle high, so it is inverted at this stage
        sck <= not sck_timer(1); -- tap 1 of a 200MHz counter is a 50MHz clock
        scken_fifo <= scken_fifo(6 downto 0) & waveform(13);
        if (sck_timer /= x"000") then
          sck_timer <= sck_timer - "1";
          active_o <= '1';
        else
          active_o <= '0';
        end if;
        if (scken_fifo(5 downto 4) = "01")  then
          -- This is tricky here, but this starting value of 259 gives you
          -- 65 pulses on tap 1.  x"104" or x"105" would also work, with 
          -- an added 5ns or 10ns delay.
          sck_timer <= x"104";
          if (adc_18bit_q = '1') then
            -- For the AD7690, we want 8 extra pulses, so the initial counter
            -- value is higher by 32.
            sck_timer <= x"124";
          end if;
        end if;
      end if;
    end if;
  end process;
      
  process(synch_i, rstn_i)
  begin
    if rising_edge(synch_i) then
      if (rstn_i = '0') then
        -- flipflop initializations:
        main_timer <= x"0000";
        waveform <= x"0000";
        sram_adr <= x"0000";
        reps <= x"00000000";
        finished <= false;
        duration <= x"0000";
        crcctl_o <= '0';
      else
        if (wpu_rst_i = '1') then
          -- WPU in reset:
          main_timer <= x"0000";
          sram_adr <= UNSIGNED(start_i);
          reps <= UNSIGNED(reps_i);
          finished <= false;
          duration <= x"0002";
        else
          -- WPU running:
          if (not finished) then
            main_timer <= main_timer + "1";
            -- check if opcode duration is reached
            if (main_timer = duration) then
              waveform <= sram_dat_i(31 downto 16);
              duration <= "0" & UNSIGNED(sram_dat_i(14 downto 0));
              crcctl_o <= sram_dat_i(15);
              -- increment SRAM address "instruction pointer"
              sram_adr <= sram_adr + "1";
              main_timer <= x"0001";
              -- check if waveform length is reached
              if (STD_LOGIC_VECTOR(sram_adr) = stop_i) then
                reps <= reps - "1";
                -- check if number of reps is reached
                if (reps = x"00000001") then
                  finished <= true;
                end if;
                sram_adr <= UNSIGNED(start_i);
              end if; -- if address = stop
            end if; -- if timer = duration
          end if; -- if not finished
        end if; -- if WPU reset; else
      end if; -- if global reset; else
    end if; -- if rising edge of clock
  end process;
end rtl;

