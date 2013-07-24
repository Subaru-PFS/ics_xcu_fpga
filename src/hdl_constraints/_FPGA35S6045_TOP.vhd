
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity FPGA35S6045_TOP is
	generic
		(
			FAST_TRAIN                        : boolean    := FALSE
		);
	port
		(
			-- PCI Express Interface
			pci_exp_txp : out std_logic;
			pci_exp_txn : out std_logic;
			pci_exp_rxp : in  std_logic;
			pci_exp_rxn : in  std_logic;

			sys_clk_p   : in  std_logic;
			sys_clk_n   : in  std_logic;
			sys_reset_n : in  std_logic;

			-- Memory Controller Block Interface
			mcb3_dram_dq                            : inout  std_logic_vector(15 downto 0);
			mcb3_dram_a                             : out std_logic_vector(14 downto 0) := (others => '0');
			mcb3_dram_ba                            : out std_logic_vector(2 downto 0);
			mcb3_dram_ras_n                         : out std_logic;
			mcb3_dram_cas_n                         : out std_logic;
			mcb3_dram_we_n                          : out std_logic;
			mcb3_dram_odt                           : out std_logic;
			mcb3_dram_cke                           : out std_logic;
			mcb3_dram_dm                            : out std_logic;
			mcb3_dram_udqs                          : inout  std_logic;
			mcb3_dram_udqs_n                        : inout  std_logic;
			mcb3_rzq                                : inout  std_logic;
			mcb3_zio                                : inout  std_logic;
			mcb3_dram_udm                           : out std_logic;
			mcb3_dram_dqs                           : inout  std_logic;
			mcb3_dram_dqs_n                         : inout  std_logic;
			mcb3_dram_ck                            : out std_logic;
			mcb3_dram_ck_n                          : out std_logic;
			mcb3_odt											 : out std_logic;

			-- Clocks and misc
			clk_27mhz_1										: in std_logic;     
			clk_27mhz_2										: in std_logic;     
			pgood_1v2										: in std_logic;      
			pgood_1v8										: in std_logic;      
			pgood_3v3										: in std_logic;      
			port_output_en_n								: out std_logic; -- 0 to connect CN4 and CN9

			-- AT93C66 SPI EEPROM
			eeprom_cs										: out std_logic;       
			eeprom_sck										: out std_logic;      
			eeprom_si										: out std_logic;       
			eeprom_so										: in std_logic;  

			port0_p											: inout std_logic_vector (11 downto 0);	
			port0_n											: inout std_logic_vector (11 downto 0);	
			port1_p											: inout std_logic_vector (11 downto 0);	
			port1_n											: inout std_logic_vector (11 downto 0);	
			port2_p											: inout std_logic_vector (19 downto 0);	
			port2_n											: inout std_logic_vector (19 downto 0)	
		);
end FPGA35S6045_TOP;

architecture rtl of FPGA35S6045_TOP is

	-------------------------
	-- Component declarations
	-------------------------
	component pcie_app_s6 is
		generic (
			FAST_TRAIN                        : boolean    := FALSE
		);
		port (
			-- PCI Express Fabric Interface
			pci_exp_txp             : out std_logic;
			pci_exp_txn             : out std_logic;
			pci_exp_rxp             : in  std_logic;
			pci_exp_rxn             : in  std_logic;

			sys_clk_p   				: in  std_logic;
			sys_clk_n   				: in  std_logic;
			sys_reset_n 				: in  std_logic;
			
			-- Local Common
			clk                    : out std_logic;
			rst_n                  : out std_logic;
	
			--  Local Read Port
			rd_addr      : out std_logic_vector(10 downto 0);
			rd_be        : out std_logic_vector(3 downto 0);
			rd_data      : in  std_logic_vector(31 downto 0);
                        
			--  Local Write Port
			wr_addr      : out std_logic_vector(10 downto 0);
			wr_be        : out std_logic_vector(7 downto 0);
			wr_data      : out std_logic_vector(31 downto 0);
			wr_en        : out std_logic;
			wr_busy      : in  std_logic	 
		);
	end component pcie_app_s6;
 
	component PIO_EP_MEM_ACCESS is
		port (
			clk          : in  std_logic;
			rst_n        : in  std_logic;

			--  Read Port
			rd_addr_i    : in  std_logic_vector(10 downto 0);
			rd_be_i      : in  std_logic_vector(3 downto 0);
			rd_data_o    : out std_logic_vector(31 downto 0);

			--  Write Port
			wr_addr_i    : in  std_logic_vector(10 downto 0);
			wr_be_i      : in  std_logic_vector(7 downto 0);
			wr_data_i    : in  std_logic_vector(31 downto 0);
			wr_en_i      : in  std_logic;
			wr_busy_o    : out std_logic
		);
	end component;

	component mig_39
		generic(
			C3_P0_MASK_SIZE           : integer := 4;
			C3_P0_DATA_PORT_SIZE      : integer := 32;
			C3_P1_MASK_SIZE           : integer := 4;
			C3_P1_DATA_PORT_SIZE      : integer := 32;
			C3_MEMCLK_PERIOD          : integer := 4000;
			C3_RST_ACT_LOW            : integer := 1;
			C3_INPUT_CLK_TYPE         : string := "OTHER";
			C3_CALIB_SOFT_IP          : string := "TRUE";
			C3_SIMULATION             : string := "FALSE";
			DEBUG_EN                  : integer := 0;
			C3_MEM_ADDR_ORDER         : string := "ROW_BANK_COLUMN";
			C3_NUM_DQ_PINS            : integer := 16;
			C3_MEM_ADDR_WIDTH         : integer := 13;
			C3_MEM_BANKADDR_WIDTH     : integer := 3
		);
		port (
			mcb3_dram_dq                            : inout  std_logic_vector(C3_NUM_DQ_PINS-1 downto 0);
			mcb3_dram_a                             : out std_logic_vector(C3_MEM_ADDR_WIDTH-1 downto 0);
			mcb3_dram_ba                            : out std_logic_vector(C3_MEM_BANKADDR_WIDTH-1 downto 0);
			mcb3_dram_ras_n                         : out std_logic;
			mcb3_dram_cas_n                         : out std_logic;
			mcb3_dram_we_n                          : out std_logic;
			--mcb3_dram_odt                           : out std_logic;
			mcb3_dram_cke                           : out std_logic;
			mcb3_dram_dm                            : out std_logic;
			mcb3_dram_udqs                          : inout  std_logic;
			mcb3_dram_udqs_n                        : inout  std_logic;
			mcb3_rzq                                : inout  std_logic;
			mcb3_zio                                : inout  std_logic;
			mcb3_dram_udm                           : out std_logic;
			c3_sys_clk                              : in  std_logic;
			c3_sys_rst_i                            : in  std_logic;
			c3_calib_done                           : out std_logic;
			c3_clk0                                 : out std_logic;
			c3_rst0                                 : out std_logic;
			mcb3_dram_dqs                           : inout  std_logic;
			mcb3_dram_dqs_n                         : inout  std_logic;
			mcb3_dram_ck                            : out std_logic;
			mcb3_dram_ck_n                          : out std_logic;
			c3_p0_cmd_clk                           : in std_logic;
			c3_p0_cmd_en                            : in std_logic;
			c3_p0_cmd_instr                         : in std_logic_vector(2 downto 0);
			c3_p0_cmd_bl                            : in std_logic_vector(5 downto 0);
			c3_p0_cmd_byte_addr                     : in std_logic_vector(29 downto 0);
			c3_p0_cmd_empty                         : out std_logic;
			c3_p0_cmd_full                          : out std_logic;
			c3_p0_wr_clk                            : in std_logic;
			c3_p0_wr_en                             : in std_logic;
			c3_p0_wr_mask                           : in std_logic_vector(C3_P0_MASK_SIZE - 1 downto 0);
			c3_p0_wr_data                           : in std_logic_vector(C3_P0_DATA_PORT_SIZE - 1 downto 0);
			c3_p0_wr_full                           : out std_logic;
			c3_p0_wr_empty                          : out std_logic;
			c3_p0_wr_count                          : out std_logic_vector(6 downto 0);
			c3_p0_wr_underrun                       : out std_logic;
			c3_p0_wr_error                          : out std_logic;
			c3_p0_rd_clk                            : in std_logic;
			c3_p0_rd_en                             : in std_logic;
			c3_p0_rd_data                           : out std_logic_vector(C3_P0_DATA_PORT_SIZE - 1 downto 0);
			c3_p0_rd_full                           : out std_logic;
			c3_p0_rd_empty                          : out std_logic;
			c3_p0_rd_count                          : out std_logic_vector(6 downto 0);
			c3_p0_rd_overflow                       : out std_logic;
			c3_p0_rd_error                          : out std_logic
		);
	end component;

	-- Local Common
	signal clk           : std_logic;
	signal rst_n         : std_logic;

	--  Local Read Port
	signal rd_addr      : std_logic_vector(10 downto 0);
	signal rd_be        : std_logic_vector(3 downto 0);
	signal rd_data      : std_logic_vector(31 downto 0);

	--  Local Write Port
	signal wr_addr      : std_logic_vector(10 downto 0);
	signal wr_be        : std_logic_vector(7 downto 0);
	signal wr_data      : std_logic_vector(31 downto 0);
	signal wr_en        : std_logic;
	signal wr_busy      : std_logic := '0';	 
	
	-- DDR Interface Signals
	signal ddr_data_wr	: std_logic;
	signal ddr_data_wr_d	: std_logic;
	signal ddr_data_wr_d1: std_logic;
	signal ddr_data_rd	: std_logic;
	signal ddr_data_rd_d	: std_logic;
	signal c3_p0_cmd_instr	: std_logic_vector (2 downto 0);
	signal c3_p0_cmd_en	: std_logic;
	signal c3_p0_rd_en	: std_logic;
	signal cmd_delay		: std_logic;	
	signal cmd_delay2		: std_logic;	
	
	-- Clock Counter Registers
	signal clk_cnt			: std_logic;
	signal clk_cnt_1		: std_logic;
	signal clk_cnt_2		: std_logic;
	signal clk_62_5MHz_cnt	: unsigned (11 downto 0);
	signal clk_27_MHz_cnt_1	: unsigned (11 downto 0);
	signal clk_27_MHz_cnt_2	: unsigned (11 downto 0);
	
	-- Register File
	constant REGISTER_COUNT		: natural := 32;
	type reg_32bit is record
		data		: std_logic_vector (31 downto 0);
		default	: std_logic_vector (31 downto 0);
		readonly	: boolean;
	end record;
	type reg_32bit_array	is array (natural range <>) of reg_32bit;
	signal register_file	: reg_32bit_array (REGISTER_COUNT-1 downto 0) := (others => (x"00000000", x"00000000", false));
	
	-- Register Locations
	constant	R_ID				: natural := 16#0000#/4;
	constant	R_STATUS			: natural := 16#0004#/4;
	constant	R_EEPROM			: natural := 16#0008#/4;
	constant	R_PORT0_IN		: natural := 16#0010#/4;
	constant	R_PORT0_OUT		: natural := 16#0014#/4;
	constant	R_PORT0_DIR		: natural := 16#0018#/4;
	constant	R_PORT1_IN		: natural := 16#0020#/4;
	constant	R_PORT1_OUT		: natural := 16#0024#/4;
	constant	R_PORT1_DIR		: natural := 16#0028#/4;
	constant	R_PORT2L_IN		: natural := 16#0030#/4;
	constant	R_PORT2L_OUT	: natural := 16#0034#/4;
	constant	R_PORT2L_DIR	: natural := 16#0038#/4;
	constant	R_PORT2H_IN		: natural := 16#0040#/4;
	constant	R_PORT2H_OUT	: natural := 16#0044#/4;
	constant	R_PORT2H_DIR	: natural := 16#0048#/4;

	constant	R_DDR_RD_DATA	: natural := 16#0050#/4;
	constant	R_DDR_WR_DATA	: natural := 16#0054#/4;
	constant	R_DDR_ADDR		: natural := 16#0058#/4;
	constant	R_DDR_STATUS	: natural := 16#005C#/4;
	
	constant	R_CLK_27_1		: natural := 16#0060#/4;
	constant	R_CLK_27_2		: natural := 16#0064#/4;
	

begin
	port_output_en_n <= '0'; -- Enable I/O ports as soon as we are configured.

	---------------------------------------------------------------------------
	-- Bus Interface
	---------------------------------------------------------------------------
	app : pcie_app_s6
		generic map (
			FAST_TRAIN 	=> FAST_TRAIN
		)
		port map (
			pci_exp_txp         => pci_exp_txp,
			pci_exp_txn         => pci_exp_txn,
			pci_exp_rxp         => pci_exp_rxp,
			pci_exp_rxn         => pci_exp_rxn,
			sys_clk_p   			=> sys_clk_p,
			sys_clk_n   			=> sys_clk_n, 
			sys_reset_n 			=> sys_reset_n,

			-- Local Common
			clk                 => clk,   
			rst_n               => rst_n, 	
			--  Local Read Port
			rd_addr      		  => rd_addr,
			rd_be        		  => rd_be,  
			rd_data             => rd_data,
			--  Local Write Port
			wr_addr             => wr_addr,
			wr_be               => wr_be,  
			wr_data             => wr_data,
			wr_en               => wr_en,  
			wr_busy             => wr_busy
		);

	-- Register File Read
	rd_data( 7 downto  0) <= register_file(TO_INTEGER(UNSIGNED(rd_addr))).data(31 downto 24);
	rd_data(15 downto  8) <= register_file(TO_INTEGER(UNSIGNED(rd_addr))).data(23 downto 16);
	rd_data(23 downto 16) <= register_file(TO_INTEGER(UNSIGNED(rd_addr))).data(15 downto  8);
	rd_data(31 downto 24) <= register_file(TO_INTEGER(UNSIGNED(rd_addr))).data( 7 downto  0);
	
	-- Register File Write
	G_REG_WRITES: for i in 0 to REGISTER_COUNT-1 generate
		process (clk, rst_n)
		begin
			if rising_edge (clk) then
				if ((rst_n = '0') or register_file(i).readonly) then
					register_file(i).data <= register_file(i).default;
					
				elsif ((wr_en = '1') and (wr_addr = STD_LOGIC_VECTOR(TO_UNSIGNED(i,11)))) then
					if (wr_be(0) = '1') then
						register_file(i).data( 7 downto  0) <= wr_data(31 downto 24);
					end if;
					if (wr_be(1) = '1') then
						register_file(i).data(15 downto  8) <= wr_data(23 downto 16);
					end if;
					if (wr_be(2) = '1') then
						register_file(i).data(23 downto 16) <= wr_data(15 downto  8);
					end if;
					if (wr_be(3) = '1') then
						register_file(i).data(31 downto 24) <= wr_data( 7 downto  0);
					end if;
				end if;
			end if;
		end process;
	end generate;

	---------------------------------------------------------------------------
	-- Mapped Registers
	---------------------------------------------------------------------------
	
	-- ID Readonly Register
	register_file(R_ID).default 	<= x"12345678";
	register_file(R_ID).readonly 	<= true;
	
	-- Power Supply Status/EEPROM Read Register
	register_file(R_STATUS).default(0) 	<= eeprom_so;
	register_file(R_STATUS).default(4) 	<= pgood_1v2;
	register_file(R_STATUS).default(5) 	<= pgood_1v8;
	register_file(R_STATUS).default(6) 	<= pgood_3v3;
	register_file(R_STATUS).readonly 	<= true;
	
	-- EEPROM Write Register (bit-bang)
	eeprom_sck	<= register_file(R_EEPROM).data(0);
	eeprom_si	<= register_file(R_EEPROM).data(1);
	eeprom_cs	<= register_file(R_EEPROM).data(2);
	
	-- Port 0
	register_file(R_PORT0_IN).readonly 	<= true;
	
	G_PORT0: for i in 0 to 11 generate
		register_file(R_PORT0_IN).default(2*i+0) 	<= port0_p(i);
		register_file(R_PORT0_IN).default(2*i+1) 	<= port0_n(i);
		
		port0_p(i) <= register_file(R_PORT0_OUT).data(2*i+0) when (register_file(R_PORT0_DIR).data(2*i+0)='1') else 'Z';
		port0_n(i) <= register_file(R_PORT0_OUT).data(2*i+1) when (register_file(R_PORT0_DIR).data(2*i+1)='1') else 'Z';
	end generate;
	
	-- Port 1
	register_file(R_PORT1_IN).readonly 	<= true;
	
	G_PORT1: for i in 0 to 11 generate
		register_file(R_PORT1_IN).default(2*i+0) 	<= port1_p(i);
		register_file(R_PORT1_IN).default(2*i+1) 	<= port1_n(i);
		
		port1_p(i) <= register_file(R_PORT1_OUT).data(2*i+0) when (register_file(R_PORT1_DIR).data(2*i+0)='1') else 'Z';
		port1_n(i) <= register_file(R_PORT1_OUT).data(2*i+1) when (register_file(R_PORT1_DIR).data(2*i+1)='1') else 'Z';
	end generate;
	
	-- Port 2 low
	register_file(R_PORT2L_IN).readonly 	<= true;
	
	G_PORT2L: for i in 0 to 15 generate
		register_file(R_PORT2L_IN).default(2*i+0) 	<= port2_p(i);
		register_file(R_PORT2L_IN).default(2*i+1) 	<= port2_n(i);
		
		port2_p(i) <= register_file(R_PORT2L_OUT).data(2*i+0) when (register_file(R_PORT2L_DIR).data(2*i+0)='1') else 'Z';
		port2_n(i) <= register_file(R_PORT2L_OUT).data(2*i+1) when (register_file(R_PORT2L_DIR).data(2*i+1)='1') else 'Z';
	end generate;

	-- Port 2 high
	register_file(R_PORT2H_IN).readonly 	<= true;
	
	G_PORT2H: for i in 16 to 19 generate
		register_file(R_PORT2H_IN).default(2*i+0-32) 	<= port2_p(i);
		register_file(R_PORT2H_IN).default(2*i+1-32) 	<= port2_n(i);
		
		port2_p(i) <= register_file(R_PORT2H_OUT).data(2*i+0-32) when (register_file(R_PORT2H_DIR).data(2*i+0-32)='1') else 'Z';
		port2_n(i) <= register_file(R_PORT2H_OUT).data(2*i+1-32) when (register_file(R_PORT2H_DIR).data(2*i+1-32)='1') else 'Z';
	end generate;
	
	---------------------------------------------------------------------------
	-- Memory Interface
	---------------------------------------------------------------------------
	u_mig_39 : mig_39
		port map (

			c3_sys_clk  			=> clk,
			c3_sys_rst_i   		=> rst_n,

			-- Connections to DDR2 Chip
			mcb3_dram_dq 			=> mcb3_dram_dq,  
			mcb3_dram_a 			=> mcb3_dram_a(12 downto 0),  
			mcb3_dram_ba 			=> mcb3_dram_ba,
			mcb3_dram_ras_n 		=> mcb3_dram_ras_n,                        
			mcb3_dram_cas_n 		=> mcb3_dram_cas_n,                        
			mcb3_dram_we_n 		=> mcb3_dram_we_n,
			--mcb3_dram_odt			=> mcb3_dram_odt,
			mcb3_dram_cke 			=> mcb3_dram_cke,                          
			mcb3_dram_ck 			=> mcb3_dram_ck,                          
			mcb3_dram_ck_n 		=> mcb3_dram_ck_n,       
			mcb3_dram_dqs 			=> mcb3_dram_dqs,                          
			mcb3_dram_dqs_n 		=> mcb3_dram_dqs_n,
			mcb3_dram_udqs 		=> mcb3_dram_udqs,          
			mcb3_dram_udqs_n 		=> mcb3_dram_udqs_n,
			mcb3_dram_udm 			=> mcb3_dram_udm,
			mcb3_dram_dm 			=> mcb3_dram_dm,
			mcb3_rzq        		=> mcb3_rzq,
			mcb3_zio        		=> mcb3_zio,
			
			c3_clk0					=>	 open, -- Output
			c3_rst0					=>  open, -- Output

			c3_calib_done      	=>  register_file(R_DDR_STATUS).default(31),

			c3_p0_cmd_clk        => clk,
			c3_p0_cmd_en         => c3_p0_cmd_en,
			c3_p0_cmd_instr      => c3_p0_cmd_instr, 
			c3_p0_cmd_bl         => "000001",
			c3_p0_cmd_byte_addr(29 downto 3)	=> register_file(R_DDR_ADDR).data(28 downto 2),
			c3_p0_cmd_byte_addr(2 downto 0)  => "000", -- 3 lsb are unused (Xilinx says 2, but it is actually 3)
			c3_p0_cmd_empty      => register_file(R_DDR_STATUS).default(25),
			c3_p0_cmd_full       => register_file(R_DDR_STATUS).default(24),
			c3_p0_wr_clk         => clk,
			c3_p0_wr_en          => ddr_data_wr_d,
			c3_p0_wr_mask        => "0000",
			c3_p0_wr_data        => register_file(R_DDR_WR_DATA).data,
			c3_p0_wr_full        => register_file(R_DDR_STATUS).default(7),
			c3_p0_wr_empty       => register_file(R_DDR_STATUS).default(6),
			c3_p0_wr_count       => register_file(R_DDR_STATUS).default(22 downto 16),
			c3_p0_wr_underrun    => register_file(R_DDR_STATUS).default(5),
			c3_p0_wr_error       => register_file(R_DDR_STATUS).default(4),
			c3_p0_rd_clk         => clk,
			c3_p0_rd_en          => c3_p0_rd_en,
			c3_p0_rd_data        => register_file(R_DDR_RD_DATA).default,
			c3_p0_rd_full        => register_file(R_DDR_STATUS).default(3),
			c3_p0_rd_empty       => register_file(R_DDR_STATUS).default(2),
			c3_p0_rd_count       => register_file(R_DDR_STATUS).default(14 downto 8),
			c3_p0_rd_overflow    => register_file(R_DDR_STATUS).default(1),
			c3_p0_rd_error       => register_file(R_DDR_STATUS).default(0)
		);
		c3_p0_rd_en <= not register_file(R_DDR_STATUS).default(2); -- c3_p0_rd_empty
		
		register_file(R_DDR_RD_DATA).readonly <= true;
		register_file(R_DDR_STATUS).readonly  <= true;
		
		process (clk)
		begin
			if rising_edge(clk) then
				----------------------------------------------------------
				-- Writes are triggered by writing to the WR_DATA register
				----------------------------------------------------------
				if ((wr_en = '1') and (wr_addr = STD_LOGIC_VECTOR(TO_UNSIGNED(R_DDR_WR_DATA,11)))) then
					ddr_data_wr <= '1';
				else
					ddr_data_wr <= '0';
				end if;

				ddr_data_wr_d1 <= ddr_data_wr;
				
				-- For unknow reasons, we need to write the data twice
				if (ddr_data_wr_d1 = '1' or ddr_data_wr = '1') then
					ddr_data_wr_d <= '1';
				else
					ddr_data_wr_d <= '0';
				end if;
				
				-- Delay command register until write data is in FIFO
				cmd_delay <= ddr_data_wr_d1;
				cmd_delay2 <= cmd_delay;
				
				----------------------------------------------------------
				-- Reads are triggered by writing to the ADDR register
				----------------------------------------------------------
				if ((wr_en = '1') and (wr_addr = STD_LOGIC_VECTOR(TO_UNSIGNED(R_DDR_ADDR,11)))) then
					ddr_data_rd <= '1';
				else
					ddr_data_rd <= '0';
				end if;
				
				ddr_data_rd_d <= ddr_data_rd or cmd_delay2; -- Read after write
				
				----------------------------------------------------------
				-- Issue command to MCB
				----------------------------------------------------------
				if (cmd_delay = '1')  then
					c3_p0_cmd_en <= '1';
					c3_p0_cmd_instr <= "000"; -- Write command
				
				else
					c3_p0_cmd_en <= ddr_data_rd_d;
					c3_p0_cmd_instr <= "001"; -- Read command
					
				end if;
			end if;
		end process;

	---------------------------------------------------------------------------
	-- Test Clocks
	---------------------------------------------------------------------------
	-- Reference counter based on 62.5 MHz clock
	process (clk)
	begin
		if rising_edge(clk) then
			if (rst_n = '0') then
				clk_cnt <= '0';
				clk_62_5MHz_cnt <= (others => '0');
				
			else
				if (clk_62_5MHz_cnt = x"0271") then -- 625 decimal
					clk_cnt <= '0';
					
				else
					clk_62_5MHz_cnt <= clk_62_5MHz_cnt + 1;
					clk_cnt <= '1';
				end if;
			end if;
		end if;
	end process;

	-- Count first 27 MHz clock
	process (clk_27mhz_1)
	begin
		if rising_edge(clk_27mhz_1) then
			clk_cnt_1	<= clk_cnt; -- Clock domain translation
			if (rst_n = '0') then
				clk_27_MHz_cnt_1 <= (others => '0');
			else
				if (clk_cnt_1 = '1') then 
					clk_27_MHz_cnt_1 <= clk_27_MHz_cnt_1 + 1;
				end if;
			end if;
		end if;
	end process;
	register_file(R_CLK_27_1).default(11 downto 0) 	<= STD_LOGIC_VECTOR(clk_27_MHz_cnt_1);
	register_file(R_CLK_27_1).readonly 	<= true;

	-- Count second 27 MHz clock
	process (clk_27mhz_2)
	begin
		if rising_edge(clk_27mhz_2) then
			clk_cnt_2	<= clk_cnt; -- Clock domain translation
			if (rst_n = '0') then
				clk_27_MHz_cnt_2 <= (others => '0');
			else
				if (clk_cnt_2 = '1') then 
					clk_27_MHz_cnt_2 <= clk_27_MHz_cnt_2 + 1;
				end if;
			end if;
		end if;
	end process;
	register_file(R_CLK_27_2).default(11 downto 0) 	<= STD_LOGIC_VECTOR(clk_27_MHz_cnt_2);
	register_file(R_CLK_27_2).readonly 	<= true;

	
end rtl;
