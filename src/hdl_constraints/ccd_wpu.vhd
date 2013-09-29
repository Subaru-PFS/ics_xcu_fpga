
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

-- This entity is the "waveform processor unit" for CCD control lines.
-- It reads 32 bit "opcodes" from blockram, interprets them as a waveform
-- description, and drives 16 digital outputs accordingly.
-- The format of a WPU opcode is simple.  The lower 16 bits are a timestamp
-- and the upper 16 bits are the values that the outputs transition to at that
-- timestamp.  Timestamps are in 40ns (25MHz) increments.
--
-- The "len" and "reps" inputs are driven by the register file.  After "len"
-- opcodes, the waveform is over and the "instruction pointer" rolls over to
-- zero.  This loop occurs "reps" times, after which time the WPU stalls in a
-- finished state.
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
    synch_i		: in  std_logic;
    clk_200mhz_i	: in  std_logic;
    rstn_i		: in  std_logic;
    
    -- SRAM interface
    sram_adr_o		: out std_logic_vector (15 downto 0);
    sram_dat_i		: in  std_logic_vector (31 downto 0);
    
    -- control signals to and from register block
    wpu_rst_i		: in  std_logic;
    len_i		: in  std_logic_vector (15 downto 0);
    reps_i		: in  std_logic_vector (31 downto 0);
    reps_o		: out std_logic_vector (31 downto 0);
    
    -- waveform output
    waveform_o		: out std_logic_vector (15 downto 0);

    -- active_o indicates that ADC SCK is active
    active_o		: out std_logic
  );
end ccd_wpu;

architecture rtl of ccd_wpu is

  -- signals
  signal main_timer	: unsigned (15 downto 0);
  signal sck_timer	: unsigned (11 downto 0);
  signal sck		: std_logic;
  signal scken_fifo	: std_logic_vector (7 downto 0);
  signal waveform	: std_logic_vector (15 downto 0);
  signal sram_adr	: unsigned (15 downto 0);
  signal reps		: unsigned (31 downto 0);
  signal finished	: boolean;

begin
  -- output ports
  sram_adr_o <= STD_LOGIC_VECTOR(sram_adr);
  waveform_o(13) <= sck; -- SCK gets special treatment
  waveform_o(15 downto 14) <= waveform(15 downto 14);
  waveform_o(12 downto 0) <= waveform(12 downto 0);
  reps_o <= STD_LOGIC_VECTOR(reps);

  process(clk_200mhz_i, rstn_i)
  begin
    if rising_edge(clk_200mhz_i) then
      if (rstn_i = '0') then
        sck <= '0';
        sck_timer <= x"000";
        scken_fifo <= x"00";
        active_o <= '0';
      else
        sck <= sck_timer(1); -- tap 1 of a 200MHz counter is a 50MHz clock
        scken_fifo <= scken_fifo(6 downto 0) & waveform(13);
        if (sck_timer /= x"000") then
          sck_timer <= sck_timer - "1";
          active_o <= '1';
        else
          active_o <= '0';
        end if;
        if ((scken_fifo(5) = '0') and (scken_fifo(4) = '1')) then
          -- This is tricky here, but this starting value of 259 gives you
          -- 65 pulses on tap 1.  x"104" or x"105" would also work, with 
          -- an added 5ns or 10ns delay.
          sck_timer <= x"103";
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
      else
        if (wpu_rst_i = '1') then
          -- WPU in reset:
          main_timer <= x"0000";
          sram_adr <= x"0000";
          reps <= UNSIGNED(reps_i);
          finished <= false;
        else
          -- WPU running:
          if (not finished) then
            main_timer <= main_timer + "1";
            -- check if opcode timestamp matches timer:
            if (STD_LOGIC_VECTOR(main_timer) = sram_dat_i(15 downto 0)) then
              waveform <= sram_dat_i(31 downto 16);
              -- increment SRAM address "instruction pointer"
              sram_adr <= sram_adr + "100";
              -- check if waveform length is reached
              if (STD_LOGIC_VECTOR(sram_adr(15 downto 2))
                  = len_i(13 downto 0)) then
                reps <= reps - "1";
                -- check if number of reps is reached
                if (reps = x"00000001") then
                  finished <= true;
                end if;
                --sram_adr <= x"0000";
                sram_adr <= x"0004";
                --main_timer <= x"0000";
                main_timer <= x"0001";
              end if; -- if address = len
            end if; -- if timer = time in opcode
          end if; -- if not finished
        end if; -- if WPU reset; else
      end if; -- if global reset; else
    end if; -- if rising edge of clock
  end process;
end rtl;

