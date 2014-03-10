
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

-- This module deserializes and stores the ADC data coming back from the FEE.
-- After the ADC is active and then goes inactive, it begins sending data
-- to the DRAM.

-- Most of this module is clocked at 62.5MHz as that is the domain that the 
-- DDR interface is in.  The sck_active input is clocked from the 25MHz
-- domain, but we put it in a FIFO for a delay anyway so that is not a problem.
-- The ADC data is clocked in by the 50MHz adc_sck_i.  The way we handle the
-- domain transition between 50MHz and 62.5MHz is that we take advantage of
-- the fact that the 50MHz clock is inactive most of the time.  We wait until
-- we know it is inactive, which means the data is stable, and then we start
-- working with that data in the 62.5MHz domain.

-- In this application, we have on the order of 13us between ADC bursts, which
-- is an eternity at 62.5MHz.  We have 16 bytes of data to move to DRAM and
-- then 600 clock cycles to sit on our hands.

-- This code now supports two different ways of clocking in serial data.  The
-- default way simply uses the SCK return as a clock.  The optional way uses
-- a 200MHz clock, and registers SCK as a data line along with the MISO lines.
-- The AD7686 datasheet says that MOSI changes while SCK is low, and data is
-- valid on both the rising edge and the falling edge.  The optional clocking
-- scheme works by saving a MOSI state from when SCK was high.

entity deserializer is
  port (
    -- clock and reset
    clk_62mhz_i         : in  std_logic;
    rstn_i              : in  std_logic;
    clk_200mhz_i        : in  std_logic;

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

    -- test_pattern = 1 means ignore MISO lines and return test pattern
    test_pattern_i      : in  std_logic
  );
end deserializer;

architecture rtl of deserializer is

  constant crc_poly     : std_logic_vector(15 downto 0) := x"a001";

  type state_type is (
    s_idle,
    s_wrdata,
    s_wrcrc,
    s_crc1,
    s_crc2
  );
  signal state          : state_type;

  -- 50MHz domain registers:
  signal dat_a          : std_logic_vector(63 downto 0);
  signal dat_b          : std_logic_vector(63 downto 0);
  -- 200MHz domain registers:
  signal dat_a2         : std_logic_vector(63 downto 0);
  signal dat_b2         : std_logic_vector(63 downto 0);
  signal sck_q          : std_logic_vector(3 downto 0);
  signal miso_a_q       : std_logic_vector(3 downto 0);
  signal miso_b_q       : std_logic_vector(3 downto 0);

  -- 62.5MHz domain registers:
  signal dat_q          : std_logic_vector(127 downto 0);
  -- active_fifo keeps a delayed record of the sck_active signal.  It is 6
  -- deep, which is overkill, but we have plenty of time and this allows for
  -- any excessive delays that the FEE and cables might introduce.
  signal active_fifo    : std_logic_vector(5 downto 0);
  signal crcctl_fifo    : std_logic_vector(2 downto 0);

  signal bytes          : unsigned(3 downto 0);

  signal crc_out        : std_logic_vector(15 downto 0);
  signal crc_count      : unsigned(2 downto 0);
  signal testx          : unsigned(31 downto 0);

begin

  ddr_wr_data_o <= dat_q(31 downto 0);

  -- This process implements the "default" deserialization method.
  process(adc_sck_i, rstn_i)
  begin -- This is the only 50MHz process
    if rising_edge(adc_sck_i) then
      if (rstn_i = '0') then
        testx        <= x"00000000";
        dat_a        <= (others => '0');
        dat_b        <= (others => '0');
      else
        dat_a <= dat_a(62 downto 0) & adc_miso_a_i;
        dat_b <= dat_b(62 downto 0) & adc_miso_b_i;
        testx <= testx + 1;
      end if;
    end if;
  end process;

  -- This process implements the "optional" deserialization method.
  process(clk_200mhz_i, rstn_i)
  begin
    if rising_edge(clk_200mhz_i) then
      if (rstn_i = '0') then
        dat_a2       <= (others => '0');
        dat_b2       <= (others => '0');
        sck_q        <= x"0";
        miso_a_q     <= x"0";
        miso_b_q     <= x"0";
      else
        sck_q    <= sck_q(2 downto 0) & adc_sck_i;
        miso_a_q <= miso_a_q(2 downto 0) & adc_miso_a_i;
        miso_b_q <= miso_b_q(2 downto 0) & adc_miso_b_i;
        if (sck_q(3 downto 2) = "10") then -- sck falling edge
          -- store the mosi values from the last time slice where
          -- SCK was high.
          dat_a2 <= dat_a2(62 downto 0) & miso_a_q(3);
          dat_b2 <= dat_b2(62 downto 0) & miso_b_q(3);
        end if;
      end if;
    end if;
  end process;

  process(clk_62mhz_i, rstn_i)
  begin
    if rising_edge(clk_62mhz_i) then
      if (rstn_i = '0') then
        -- flip-flop initializations
        dat_q        <= (others => '0');
        active_fifo  <= "000000";
        crcctl_fifo  <= "000";
        ddr_wr_en_o  <= '0';
        bytes        <= x"0";
        crc_out      <= x"0000";
        crc_count    <= "000";
      else
        active_fifo <= active_fifo(4 downto 0) & sck_active_i;
        crcctl_fifo <= crcctl_fifo(1 downto 0) & crcctl_i;
        if (crcctl_fifo(2 downto 1) = "10") then
          -- reset crc on crcctl falling edge
          crc_out <= x"0000";
        end if;
        -- After data is deserialized, this state machine sends it to the FIFO
        -- and calculates a CRC of it.
        case (state) is
          when s_idle =>
            bytes <= x"0";
            -- comment out this line to use the optional clocking method:
            -- dat_q <= dat_b & dat_a;
            -- comment out this line to use the default clocking method:
            dat_q <= dat_b2 & dat_a2;
            -- We could assign words to dat_q with any ordering
            -- that is convenient for the CPU.
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
              state <= s_wrcrc;
              dat_q(31 downto 16) <= x"cccc"; -- magic number indicates CRC
              dat_q(15 downto 0) <= crc_out;
              ddr_wr_en_o <= '1';
            end if;
          when s_wrcrc =>
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

