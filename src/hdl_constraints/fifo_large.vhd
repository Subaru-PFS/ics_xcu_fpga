
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

-- This component is a FIFO that is 32 bits wide and about 16M deep.  It uses
-- an external DRAM for this storage, and two internal FIFOs.
-- Data passes through fifo_in and then fifo_out.  DRAM is only used as a
-- backup if fifo_out fills up and 64 words are available in fifo_in.  DRAM
-- is always accessed with 64 word bursts.

-- In this FPGA design, all code with any knowledge of the Xilinx memory
-- interface to the DDR2 RAM is in this component.  It is designed so that
-- multiple FIFO components could share the DRAM as long as they used separate
-- regions, but at this time there is only one.  To do a memory interface
-- read, you send a read command, wait for read data to be available, and then
-- read it.  To do a memory interface write, you write data and then send a
-- write command.  These transactions are implemented in the state machine
-- in this component.

-- The write port of the input FIFO and the read port of the output FIFO are
-- controlled directly by external logic.

-- This FIFO does not check for overflows.  If it runs out of DRAM storage,
-- data will just be lost.  Our intended usage is to store one 36MB image at
-- a time, and we address 64MB of DRAM.  We could easily expand to the full
-- 128MB of DRAM.

-- The rd_data_count_o output from this component only tells the user how
-- many words are available in fifo_out.  This will max out around 300 even
-- when millions of words are queued, but that suffices to get read
-- overhead down to a reasonable level.  The memory interface can have
-- unexpected delays due to refresh cycles, so we don't want to promise more
-- than what is guaranteed to be available for fast reading.

entity fifo_large is
  port (
    -- clock and reset for memory interface domain
    clk_i               : in  std_logic;
    rstn_i              : in  std_logic;
    rd_rst_i            : in  std_logic;
    wr_rst_i            : in  std_logic;

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

    -- debug
    head_o              : out std_logic_vector(23 downto 0);
    tail_o              : out std_logic_vector(23 downto 0);

    -- optional DDR arbitration
    ddr_req_o           : out std_logic;
    ddr_grant_i         : in  std_logic;

    -- write slave interface
    wr_clk_i            : in std_logic;
    wr_data_count_o     : out std_logic_vector(9 downto 0);
    data_i              : in std_logic_vector(31 downto 0);
    wr_en_i             : in std_logic;
    full_o              : out std_logic;

    -- read slave interface
    rd_clk_i            : in std_logic;
    rd_en_i             : in std_logic;
    data_o              : out std_logic_vector(31 downto 0);
    empty_o             : out std_logic;
    rd_data_count_o     : out std_logic_vector(9 downto 0)
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
      rd_data_count : out std_logic_vector(9 downto 0);
      wr_data_count : out std_logic_vector(9 downto 0)
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

  -- fifo_in interface
  signal fifo_rd        : std_logic;
  signal fifo_dout      : std_logic_vector(31 downto 0);
  signal rd_count       : std_logic_vector(9 downto 0);
  signal fifo_empty     : std_logic;

  -- fifo_out interface
  signal fifo_wr        : std_logic;
  signal fifo_din       : std_logic_vector(31 downto 0);
  signal wr_count       : std_logic_vector(9 downto 0);
  signal fifo_full      : std_logic;

  -- head and tail are DRAM addresses
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
  head_o <= STD_LOGIC_VECTOR(head);
  tail_o <= STD_LOGIC_VECTOR(tail);

  -- Internal blockram-based FIFO instantiations:
  fifo_in : fifo_512x4byte
    port map (
      rst => not rstn_i,
      wr_clk => wr_clk_i,
      wr_data_count => wr_data_count_o,
      din => data_i,
      wr_en => wr_en_i,
      full => full_o,
  
      rd_clk => clk_i,
      rd_data_count => rd_count,
      dout => fifo_dout,
      rd_en => fifo_rd,
      empty => fifo_empty
    );

  fifo_out : fifo_512x4byte
    port map (
      rst => not rstn_i,
      wr_clk => clk_i,
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

  process(clk_i, rstn_i)
  begin
    if rising_edge(clk_i) then
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
	  -- This state machine does one 64 word (256 byte) transaction any
	  -- time it can.  All data starts in fifo_in, then moves to DDR RAM,
	  -- then move to fifo_out.  This was, the DDR maintains a record of
	  -- everything that passed through, and by doing a "read reset" and
	  -- not a "write reset" software can read the image data repeatedly.
	  --
          -- I saw some issues when writing to fifo_out on consecutive clocks.
          -- We certainly don't need that level of bandwidth anyway, so now I
          -- only assert fifo_wr if it is not already asserted.  Still,
          -- fifo_out supports 125MB/s and we read it at about 1MB/s.
          -- By the same token we don't read from fifo_in on consecutive
          -- clocks.
          when s_idle =>
            ddr_cmd_instr_o <= "001"; -- read instruction = 1
            ddr_cmd_byte_addr_o <= "0000" & STD_LOGIC_VECTOR(head) & "00";
	    if rd_rst_i = '1' then
	      head <= x"000000";
            end if;
	    if wr_rst_i = '1' then
	      tail <= x"000000";
	      fifo_rd <= not fifo_empty and not fifo_rd;
            end if;
            if (rd_count(8 downto 7) /= "00" and wr_rst_i = '0') then
              -- if incoming FIFO has 64 words in it, send them to RAM
              ddr_req_o <= '1';
              if (ddr_grant_i = '1' and ddr_wr_empty_i = '1') then
                state <= s_ddr_wr;
              end if;
            elsif (head /= tail and wr_count(8) = '0' and rd_rst_i = '0') then
              -- if outgoing FIFO can accept 64 words from RAM, fetch them
              ddr_req_o <= '1';
              if (ddr_grant_i = '1') then
                state <= s_rd_cmd;
              end if;
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

