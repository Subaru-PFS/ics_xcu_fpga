
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

-- This component serves to resynchronize the write bus coming out of the
-- PIO component.

-- This is a non-trivial resynchronizer to design because either clock domain
-- might be faster and there are no flow control or acknowledge mechanisms.
-- In actual usage here, the output domain is faster, and that is likely to 
-- always be the case, but I should not rely on that assumption.

-- This component allows for the wr_en input to strobe for several clock
-- cycles, and that only counts as one strobe.  On the output side, the
-- corresponding signals will only strobe for one clock.

-- This component relies on the assumption that its input buses do not change
-- for several clock cycles after a strobe.  This is a valid assumption, but
-- probably not guaranteed by the specification of the PIO read/write bus, if
-- such a spec even exists.

entity pio_resynch is
  port (
    -- Input clock and reset
    clk1_i        : in std_logic;
    rstn1_i       : in std_logic;
    -- Input signals
    wr_addr_i    : in std_logic_vector(10 downto 0);
    wr_be_i      : in std_logic_vector(7 downto 0);
    wr_data_i    : in std_logic_vector(31 downto 0);
    wr_en_i      : in std_logic;
    -- Output clock and reset
    clk2_i        : in std_logic;
    rstn2_i       : in std_logic;
    -- Output signals
    wr_addr_o    : out std_logic_vector(10 downto 0);
    wr_be_o      : out std_logic_vector(7 downto 0);
    wr_data_o    : out std_logic_vector(31 downto 0);
    wr_en_o      : out std_logic
  );
end pio_resynch;

architecture rtl of pio_resynch is

  -- By "sum" in my description of these registers, what I mean is a 1 bit
  -- sum; a register that toggles at every positive transition.

  -- write strobe resynch:
  signal we_q1    : std_logic; -- re-register input
  signal we_q2    : std_logic; -- edge sum, input domain
  signal we_q3    : std_logic; -- edge sum, output domain
  signal we_q4    : std_logic; -- re-register q3
  signal we_q5    : std_logic; -- re-register q4

  -- re-register everything else:
  signal q        : std_logic_vector (50 downto 0); -- 11+32+8 = 51

begin

  process(clk1_i, rstn1_i)
  begin
    if rising_edge(clk1_i) then
      if (rstn1_i = '0') then
        we_q1 <= '0';
        we_q2 <= '0';
      else
	-- before crossing clock domains we turn each posedge into a toggle
	we_q1 <= wr_en_i;
	if wr_en_i = '1' and we_q1 = '0' then
	  we_q2 <= not we_q2;
	end if;
      end if;
    end if;
  end process;

  process(clk2_i, rstn2_i)
  begin
    if rising_edge(clk2_i) then
      if (rstn2_i = '0') then
        we_q3 <= '0';
        we_q4 <= '0';
        we_q5 <= '0';
	q <= (others => '0');
        wr_addr_o <= (others => '0');
        wr_be_o <= (others => '0');
        wr_data_o <= (others => '0');
        wr_en_o <= '0';
      else
	-- after crossing clock domains and sufficient reregistering, 
	-- we turn each toggle into a 1 clock strobe
        we_q3 <= we_q2;
        we_q4 <= we_q3;
        we_q5 <= we_q4;
	wr_en_o <= we_q4 xor we_q5;

	q <= wr_addr_i & wr_be_i & wr_data_i;
        wr_addr_o <= q(50 downto 40);
        wr_be_o <= q(39 downto 32);
        wr_data_o <= q(31 downto 0);
      end if;
    end if;
  end process;

end rtl;
