
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

-- This component is a FIFO that is 32 bits wide and about 16M deep.  It uses
-- an external DRAM for this storage, and two internal FIFOs.
-- Data passes through fifo_in and then fifo_out.  DRAM is only used as a
-- backup if fifo_out fills up and 64 words are available in fifo_in.  DRAM
-- is always accessed with 64 word bursts.

entity fifo_large is
  port (
    -- clock and reset for memory interface domain
    clk_62mhz_i         : in  std_logic;
    rstn_i              : in  std_logic;

    -- DDR RAM interface
    ddr_cmd_en_o        : out std_logic;
    ddr_cmd_instr_o     : out std_logic_vector(2 downto 0);
    ddr_cmd_byte_addr_o : out std_logic_vector(29 downto 0);
    ddr_cmd_bl_o        : out std_logic_vector(5 downto 0);
    ddr_cmd_empty_i     : in  std_logic;
    ddr_cmd_full_i      : in  std_logic;
    ddr_wr_en_o         : out std_logic;
    ddr_wr_data_o       : out std_logic_vector(31 downto 0);
    ddr_wr_full_i       : in  std_logic;
    ddr_wr_empty_i      : in  std_logic;
    ddr_rd_en_o         : out std_logic;
    ddr_rd_data_i       : in  std_logic_vector(31 downto 0);
    ddr_rd_empty_i      : in  std_logic;

    -- optional DDR arbitration
    ddr_req_o           : out std_logic;
    ddr_grant_i         : in  std_logic;

    -- write slave interface
    wr_clk_i            : in std_logic;
    wr_data_count_o     : out std_logic_vector(8 downto 0);
    data_i              : in std_logic_vector(31 downto 0);
    wr_en_i             : in std_logic;
    full_o              : out std_logic;

    -- read slave interface
    rd_clk_i            : in std_logic;
    rd_en_i             : in std_logic;
    data_o              : out std_logic_vector(31 downto 0);
    empty_o             : out std_logic;
    rd_data_count_o     : out std_logic_vector(8 downto 0)
  );
end fifo_large;

architecture rtl of fifo_large is

  component fifo_512x4byte
    port (
      rst : in std_logic;
      wr_clk : in std_logic;
      rd_clk : in std_logic;
      din : in std_logic_vector(31 downto 0);
      wr_en : in std_logic;
      rd_en : in std_logic;
      dout : out std_logic_vector(31 downto 0);
      full : out std_logic;
      empty : out std_logic;
      rd_data_count : out std_logic_vector(8 downto 0);
      wr_data_count : out std_logic_vector(8 downto 0)
    );
  end component;

  type state_type is (
    s_idle,
    s_ddr_wr,
    s_wr_cmd,
    s_rd_cmd,
    s_ddr_rd
  );
  signal state          : state_type;

  signal fifo_rd        : std_logic;
  signal fifo_dout      : std_logic_vector(31 downto 0);
  signal rd_count       : std_logic_vector(8 downto 0);
  signal fifo_empty     : std_logic;

  signal fifo_wr        : std_logic;
  signal fifo_din       : std_logic_vector(31 downto 0);
  signal wr_count       : std_logic_vector(8 downto 0);
  signal fifo_full      : std_logic;

  signal head           : unsigned(23 downto 0);
  signal tail           : unsigned(23 downto 0);
  signal words          : unsigned(5 downto 0);
  signal ddr_rd_en      : std_logic;
  signal ddr_wr_en      : std_logic;

begin

  ddr_rd_en_o <= ddr_rd_en;
  ddr_wr_en_o <= ddr_wr_en;
  ddr_cmd_bl_o <= "111111"; -- 64 word burst length
  ddr_wr_data_o <= fifo_dout;

  fifo_in : fifo_512x4byte
    port map (
      rst => not rstn_i,
      wr_clk => wr_clk_i,
      wr_data_count => wr_data_count_o,
      din => data_i,
      wr_en => wr_en_i,
      full => full_o,
  
      rd_clk => clk_62mhz_i,
      rd_data_count => rd_count,
      dout => fifo_dout,
      rd_en => fifo_rd,
      empty => fifo_empty
    );

  fifo_out : fifo_512x4byte
    port map (
      rst => not rstn_i,
      wr_clk => clk_62mhz_i,
      wr_data_count => wr_count,
      din => fifo_din,
      wr_en => fifo_wr,
      full => fifo_full,
  
      rd_clk => rd_clk_i,
      rd_data_count => rd_data_count_o,
      dout => data_o,
      rd_en => rd_en_i,
      empty => empty_o
    );

  process (fifo_dout, ddr_rd_data_i, ddr_rd_en)
  begin
    if (ddr_rd_en = '1') then
      fifo_din <= ddr_rd_data_i;
    else
      fifo_din <= fifo_dout;
    end if;
  end process;

  process(clk_62mhz_i, rstn_i)
  begin
    if rising_edge(clk_62mhz_i) then
      if (rstn_i = '0') then
        state <= s_idle;
        fifo_rd <= '0';
        fifo_wr <= '0';
        head <= x"000000";
        tail <= x"000000";
        ddr_rd_en <= '0';
        ddr_wr_en <= '0';
        words <= "000000";
        ddr_cmd_en_o <= '0';
        ddr_cmd_instr_o <= "000";
        ddr_cmd_byte_addr_o <= (others => '0');
        ddr_req_o <= '0';
      else
        fifo_rd <= '0';
        fifo_wr <= '0';
        ddr_rd_en <= '0';
        ddr_wr_en <= '0';
        ddr_cmd_en_o <= '0';

        case (state) is
          when s_idle =>
            ddr_cmd_instr_o <= "001"; -- read instruction = 1
            ddr_cmd_byte_addr_o <= "0000" & STD_LOGIC_VECTOR(head) & "00";
            if (rd_count(8 downto 7) /= "00") then
              -- if incoming FIFO has 64 words in it, send them to RAM
              ddr_req_o <= '1';
              if (ddr_grant_i = '1' and ddr_wr_empty_i = '1') then
                state <= s_ddr_wr;
              end if;
            elsif ((head /= tail) and (wr_count(8 downto 7) = "00")) then
              -- if outgoing FIFO can accept 64 words from RAM, fetch them
              ddr_req_o <= '1';
              if (ddr_grant_i = '1') then
                state <= s_rd_cmd;
              end if;
            elsif (head = tail and fifo_empty = '0' and fifo_full = '0' and
	           fifo_wr = '0') then
              -- skip RAM and move from one FIFO to the other
              fifo_rd <= '1';
              fifo_wr <= '1';
            end if;

          when s_ddr_wr =>
            -- move 64 words from fifo_in to DDR
            ddr_cmd_instr_o <= "000"; -- write instruction = 0
            ddr_cmd_byte_addr_o <= "0000" & STD_LOGIC_VECTOR(tail) & "00";
            if (ddr_wr_full_i = '0' and fifo_rd = '0') then
              fifo_rd <= '1';
              ddr_wr_en <= '1';
              words <= words + "1";
              if (words = 63) then
                state <= s_wr_cmd;
                tail <= tail + 64;
              end if;
            end if;

          when s_wr_cmd =>
            -- send burst write command to memory interface
            state <= s_idle;
            ddr_cmd_en_o <= '1'; -- command parameters are already set up
            ddr_req_o <= '0';

          when s_rd_cmd =>
            -- send burst read command to memory interface
            state <= s_ddr_rd;
            ddr_cmd_en_o <= '1'; -- command parameters are already set up
            head <= head + 64;

          when s_ddr_rd =>
            -- move 64 words from DDR to fifo_out
            if (ddr_rd_empty_i = '0' and fifo_wr = '0') then
              ddr_rd_en <= '1';
              fifo_wr <= '1';
              words <= words + "1";
              if (words = 63) then
                state <= s_idle;
                ddr_req_o <= '0';
              end if;
            end if;
        end case;
      end if;
    end if;
  end process;

end rtl;

