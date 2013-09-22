
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

-- This module deserializes and stores the ADC data coming back from the FEE.
-- After the ADC is active and then goes inactive, it begins sending data
-- to the DRAM.

-- Most of this module is clocked at 62.5MHz as that is the domain that the 
-- DDR interface is in.  The sck_active input is clocked from the 100MHz
-- domain, but we put it in a FIFO for a delay anyway so that is not a problem.
-- The ADC data is clocked in by the 50MHz adc_sck_i.  The way we handle the
-- domain transition between 50MHz and 62.5MHz is that we take advantage of
-- the fact that the 50MHz clock is inactive most of the time.  We wait until
-- we know it is inactive, which means the data is stable, and then we start
-- working with that data in the 62.5MHz domain.

-- In this application, we have on the order of 1ms between ADC bursts, which
-- is an eternity at 62.5MHz.  We have 16 bytes of data to move to DRAM and
-- then 62000 clock cycles to sit on our hands.

-- Software is free to ignore the CRC output.

entity deserializer is
  port (
    -- clock and reset
    clk_62mhz_i         : in  std_logic;
    rstn_i              : in  std_logic;

    -- ADC lines from FEE
    adc_miso_a_i        : in  std_logic;
    adc_miso_b_i        : in  std_logic;
    adc_sck_i           : in  std_logic;

    -- active signal from CCD WPU indicates an ADC cycle
    sck_active_i        : in  std_logic;

    -- DDR RAM interface (This entity writes DRAM; it does not read.)
    ddr_cmd_en_o        : out std_logic;
    ddr_cmd_instr_o     : out std_logic_vector(2 downto 0);
    ddr_cmd_byte_addr_o : out std_logic_vector(29 downto 0);
    ddr_cmd_bl_o        : out std_logic_vector(5 downto 0);
    ddr_cmd_empty_i     : in  std_logic;
    ddr_cmd_full_i      : in  std_logic;
    ddr_wr_en_o         : out std_logic;
    ddr_wr_data_o       : out std_logic_vector(31 downto 0);
    ddr_wr_full_i       : in  std_logic;

    -- CRC output
    crc_o               : out std_logic_vector(15 downto 0);
    crc_rst_i           : in  std_logic;

    adr_rst_i           : in  std_logic
  );
end deserializer;

architecture rtl of deserializer is

  constant crc_poly     : std_logic_vector(15 downto 0) := x"a001";

  type state_type is (
    s_idle,
    s_wrdata,
    s_wrcmd,
    s_crc1,
    s_crc2
  );
  signal state          : state_type;

  signal dat_a          : std_logic_vector(63 downto 0);
  signal dat_b          : std_logic_vector(63 downto 0);
  signal dat_q          : std_logic_vector(127 downto 0);

  -- active_fifo keeps a delayed record of the sck_active signal.  It is 6
  -- deep, which is overkill, but we have plenty of time and this allows for
  -- any excessive delays that the FEE and cables might introduce.
  signal active_fifo    : std_logic_vector(5 downto 0);

  signal ddr_cmd_en     : std_logic;
  signal ddr_wr_en      : std_logic;
  signal adr            : unsigned(29 downto 0);
  signal bytes          : unsigned(3 downto 0);

  signal crc_out        : std_logic_vector(15 downto 0);
  signal crc_count      : unsigned(2 downto 0);

begin

  ddr_cmd_en_o <= ddr_cmd_en;
  ddr_cmd_instr_o <= "000"; -- write command
  ddr_cmd_byte_addr_o <= STD_LOGIC_VECTOR(adr);
  ddr_cmd_bl_o <= "000011"; -- 3 means burst length of 4, our whole 16 bytes
  ddr_wr_en_o <= ddr_wr_en;
  ddr_wr_data_o <= dat_q(31 downto 0);

  crc_o <= crc_out;

  process(adc_sck_i)
  begin -- This is the only 50MHz process
    if rising_edge(adc_sck_i) then
      dat_a <= dat_a(62 downto 0) & adc_miso_a_i;
      dat_b <= dat_b(62 downto 0) & adc_miso_b_i;
      dat_b <= x"deadbeef1234abcd"; -- XXX testing only!
    end if;
  end process;

  process(clk_62mhz_i, rstn_i)
  begin
    if rising_edge(clk_62mhz_i) then
      if (rstn_i = '0') then
        -- flip-flop initializations
        dat_q        <= (others => '0');
        active_fifo  <= "000000";
        ddr_cmd_en   <= '0';
        ddr_wr_en    <= '0';
        adr          <= (others => '0');
        bytes        <= x"0";
        crc_out      <= x"0000";
        crc_count    <= "000";
      else
        active_fifo <= active_fifo(4 downto 0) & sck_active_i;
        ddr_cmd_en <= '0';
        if (adr_rst_i = '1') then
          adr <= (others => '0');
        end if;
        if (crc_rst_i = '1') then
          crc_out <= x"0000";
        end if;
        case (state) is
          when s_idle =>
            bytes <= x"0";
            dat_q <= dat_b & dat_a; -- is this the data organization we want?
            if (active_fifo(5 downto 4) = "10") then
              -- sck_active falling edge means we can start storing data
              state <= s_wrdata;
              ddr_wr_en <= '1';
            end if;
          when s_wrdata =>
            dat_q <= dat_q(31 downto 0) & dat_q(127 downto 32); -- rotate by 32
            bytes <= bytes + "100";
            if (bytes = "1100") then
              ddr_wr_en <= '0';
              state <= s_wrcmd;
            end if;
          when s_wrcmd =>
            ddr_cmd_en <= '1';
            state <= s_crc1;
          -- After doing a ROR 32 4 times and sending 4 d-words to SDRAM, the
          -- data is back to where it started, and we reuse it for crc
          -- calculations.  We have 16 bytes to process, so we go to state 
          -- s_crc2 16 times.  In that state, we process 8 bits.
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
                adr <= adr + x"10";
              end if;
            end if;
        end case;
      end if;
    end if;
  end process;
end rtl;

