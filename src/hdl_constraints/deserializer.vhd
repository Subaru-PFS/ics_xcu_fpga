
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

-- This module deserializes and stores the ADC data coming back from the FEE.
-- After the ADC is active and then goes inactive, it begins sending data
-- to the DRAM.

-- Most of this module is clocked by clk_i so that it can talk directly to the
-- DDR interface.  The sck_active input is clocked from the 25MHz domain, but
-- we put it in a FIFO for a delay anyway so that is not a problem.  The
-- actual deserialization is done in the 200MHz domain, so that it gets 
-- enough samples of the 50MHz SCK and data lines to correctly record data
-- bits.  Data from the 200MHz domain is only used by the clk_i domain when
-- we know it is not changing.

-- In this application, we have on the order of 13us between ADC bursts, which
-- is an eternity at any reasonably clocking speed.

-- For now, the technique of using adc_sck_i as a clock has been abandoned, 
-- because it did not work, for unknown reasons, and the 200MHz sampling works
-- very well and is probably more reliable.

entity deserializer is
  port (
    -- clock and reset
    clk_i               : in  std_logic;
    rstn_i              : in  std_logic;
    clk_200mhz_i        : in  std_logic;

    -- Reset row count between images
    row_rst_i           : in  std_logic;

    -- ADC lines from FEE
    adc_miso_a_i        : in  std_logic;
    adc_miso_b_i        : in  std_logic;
    adc_sck_i           : in  std_logic;

    -- active signal from CCD WPU indicates an ADC cycle
    sck_active_i        : in  std_logic;
    crcctl_i            : in  std_logic;

    -- DDR RAM interface (This entity writes DRAM; it does not read.)
    ddr_wr_en_o         : out std_logic;
    ddr_wr_data_o       : out std_logic_vector(31 downto 0);

    -- adc_18bit = 1 means serial data from 18 bit AD7690
    -- adc_18bit = 0 means serial data from 16 bit AD7686
    adc_18bit_i         : in  std_logic;
    -- adc_18lowbits = 1 means drop 2*MSB
    -- adc_18lowbits = 0 means drop 2*LSB
    adc_18lowbits_i         : in  std_logic;

    -- test_pattern = 1 means ignore MISO lines and return test pattern
    test_pattern_i      : in  std_logic
  );
end deserializer;

architecture rtl of deserializer is

  constant crc_poly     : std_logic_vector(15 downto 0) := x"a001";

  type state_type is (
    s_idle,
    s_wrdata,
    s_wrmeta1, -- states for writing metadata at the end of a row
    s_wrmeta2,
    s_wrmeta3,
    s_crc1,
    s_crc2
  );
  signal state          : state_type;

  -- 200MHz domain registers:
  signal dat_a          : std_logic_vector(71 downto 0);
  signal dat_b          : std_logic_vector(71 downto 0);
  signal sck_q          : std_logic_vector(3 downto 0);
  signal miso_a_q       : std_logic_vector(3 downto 0);
  signal miso_b_q       : std_logic_vector(3 downto 0);
  signal testx          : unsigned(31 downto 0);

  -- clk_i domain registers:
  signal dat_q          : std_logic_vector(127 downto 0);
  -- active_fifo keeps a delayed record of the sck_active signal.  It is 6
  -- deep, which is overkill, but we have plenty of time and this allows for
  -- any excessive delays that the FEE and cables might introduce.
  signal active_fifo    : std_logic_vector(5 downto 0);
  signal crcctl_fifo    : std_logic_vector(2 downto 0);

  signal bytes          : unsigned(3 downto 0);
  signal row            : unsigned(15 downto 0);

  signal crc_out        : std_logic_vector(15 downto 0);
  signal crc_count      : unsigned(2 downto 0);

begin

  ddr_wr_data_o <= dat_q(31 downto 0);

  -- This process implements the deserialization at 200MHz.
  process(clk_200mhz_i, rstn_i)
  begin
    if rising_edge(clk_200mhz_i) then
      if (rstn_i = '0') then
        dat_a        <= (others => '0');
        dat_b        <= (others => '0');
        sck_q        <= x"0";
        miso_a_q     <= x"0";
        miso_b_q     <= x"0";
        testx        <= x"00000000";
      else
        sck_q    <= sck_q(2 downto 0) & adc_sck_i;
        miso_a_q <= miso_a_q(2 downto 0) & adc_miso_a_i;
        miso_b_q <= miso_b_q(2 downto 0) & adc_miso_b_i;
        if (sck_q(3 downto 2) = "10") then -- sck falling edge
          -- store the mosi values from the last time slice where
          -- SCK was high.
          dat_a <= dat_a(70 downto 0) & miso_a_q(3);
          dat_b <= dat_b(70 downto 0) & miso_b_q(3);
          testx <= testx + 1;
        end if;
      end if;
    end if;
  end process;

  process(clk_i, rstn_i)
  begin
    if rising_edge(clk_i) then
      if (rstn_i = '0') then
        -- flip-flop initializations
        dat_q        <= (others => '0');
        active_fifo  <= "000000";
        crcctl_fifo  <= "000";
        ddr_wr_en_o  <= '0';
        bytes        <= x"0";
        row          <= x"0000";
        crc_out      <= x"0000";
        crc_count    <= "000";
      else
        active_fifo <= active_fifo(4 downto 0) & sck_active_i;
        crcctl_fifo <= crcctl_fifo(1 downto 0) & crcctl_i;
        if (crcctl_fifo(2 downto 1) = "10") then
          -- reset crc on crcctl falling edge
          crc_out <= x"0000";
        end if;
        if (row_rst_i = '1') then
          row          <= x"0000";
        end if;
        -- After data is deserialized, this state machine sends it to the FIFO
        -- and calculates a CRC of it.
        case (state) is
          when s_idle =>
            bytes <= x"0";
            -- We could assign words to dat_q with any ordering
            -- that is convenient for the CPU.
            -- 16 bit ADC version:
            dat_q <= dat_b(63 downto 0) & dat_a(63 downto 0);
            -- 18 bit ADC version:
            if (adc_18bit_i = '1') then
              if (adc_18lowbits_i = '0') then
                -- We want to discard the MSB and LSB from each 18 bit word.
                -- The MSB is thrown out because it is the sign bit and we assume
                -- we don't get negative voltages.  The LSB is thrown out because
                -- we only need 16 bits of data.  Actual negative voltages will
                -- show up as large positive voltages.
                dat_q(15 downto 0) <= dat_a(16 downto 1);
                dat_q(31 downto 16) <= dat_a(34 downto 19);
                dat_q(47 downto 32) <= dat_a(52 downto 37);
                dat_q(63 downto 48) <= dat_a(70 downto 55);
                dat_q(79 downto 64) <= dat_b(16 downto 1);
                dat_q(95 downto 80) <= dat_b(34 downto 19);
                dat_q(111 downto 96) <= dat_b(52 downto 37);
                dat_q(127 downto 112) <= dat_b(70 downto 55);
              else    
                -- We want to discard two LSBs from each 18 bit word.
                dat_q(15 downto 0) <= dat_a(17 downto 2);
                dat_q(31 downto 16) <= dat_a(35 downto 20);
                dat_q(47 downto 32) <= dat_a(53 downto 38);
                dat_q(63 downto 48) <= dat_a(71 downto 56);
                dat_q(79 downto 64) <= dat_b(17 downto 2);
                dat_q(95 downto 80) <= dat_b(35 downto 20);
                dat_q(111 downto 96) <= dat_b(53 downto 38);
                dat_q(127 downto 112) <= dat_b(71 downto 56);
              end if;
              -- If we want negative voltages to be written as zeros or some
              -- other special warning value, we could stick that 
              -- transformation here.
            end if;
            -- test pattern overrides real data:
            if (test_pattern_i = '1') then
              dat_q <= STD_LOGIC_VECTOR(testx) &
                       STD_LOGIC_VECTOR(testx) &
                       STD_LOGIC_VECTOR(testx) &
                       STD_LOGIC_VECTOR(testx) ;
            end if;
            if (active_fifo(5 downto 4) = "10") then
              -- sck_active falling edge means we can start storing data
              state <= s_wrdata;
              ddr_wr_en_o <= '1';
            end if;
            if (crcctl_fifo(2 downto 1) = "01") then
              -- crcctl rising edge requests a CRC stored in the data stream.
              state <= s_wrmeta1;
              dat_q(31 downto 16) <= x"0005"; -- 0005 = line mark with row #
              dat_q(15 downto 0) <= STD_LOGIC_VECTOR(row);
              row <= row + 1;
              ddr_wr_en_o <= '1';
            end if;
          when s_wrmeta1 =>
            ddr_wr_en_o <= '0';
            state <= s_wrmeta2;
          when s_wrmeta2 =>
            dat_q(31 downto 16) <= crc_out;
            dat_q(15 downto 0) <= x"000a"; -- 000a = line mark with CRC
            ddr_wr_en_o <= '1';
            state <= s_wrmeta3;
          when s_wrmeta3 =>
            ddr_wr_en_o <= '0';
            state <= s_idle;
          when s_wrdata =>
            dat_q <= dat_q(31 downto 0) & dat_q(127 downto 32); -- rotate by 32
            bytes <= bytes + "100";
            if (bytes = "1100") then
              ddr_wr_en_o <= '0';
              state <= s_crc1;
            end if;
          -- After doing a ROR 32 4 times and sending 4 d-words to SDRAM, the
          -- data is back to where it started, and we reuse it for crc
          -- calculations.  We have 16 bytes to process, so we go to state 
          -- s_crc2 16 times.  In that state, we process 8 bits.
          -- Refer to take_image.c, which performs the exact same algorithm
          -- in order to check the CRC.
          when s_crc1 =>
            bytes <= bytes + "1";
            crc_out <= crc_out xor x"00" & dat_q(7 downto 0);
            dat_q <= dat_q(7 downto 0) & dat_q(127 downto 8); -- rotate by 8
            crc_count <= "000";
            state <= s_crc2;
          when s_crc2 =>
            if (crc_out(0) = '1') then
              crc_out <= '0' & crc_out(15 downto 1) xor crc_poly;
            else
              crc_out <= '0' & crc_out(15 downto 1);
            end if;
            crc_count <= crc_count + "1";
            if (crc_count = "111") then
              state <= s_crc1;
              if (bytes = x"0") then
                state <= s_idle;
              end if;
            end if;
        end case;
      end if;
    end if;
  end process;
end rtl;

