
------------------------------------------------------------------------------
-- This is the top level component for this FPGA design.  This design is for
-- the Subaru PFS back end electronics (BEE).  The BEE consists of two boards,
-- a single board computer module and an FPGA module.  At this time the
-- computer board is a 1.2GHz Celeron from RTD.  This FPGA code is expected to
-- be portable to other platforms if necessary. The two modules are connected
-- by a stackable PCIe bus connector.  The FPGA is a PCIe endpoint for the CPU.

-- The boilerplate codebase provided by Xilinx and RTD included a PIO entity,
-- (programmed IO) which handles 32 bit read and write accesses from the PCIe
-- root, and a "register file" structure that the PIO can read and write.  It
-- also included a memory interface module to connect to the 128MB DDR2 RAM
-- that is on the FPGA board.

-- The memory interface is being used as is.  The PIO code was only modified
-- slightly so that our logic can know when a read cycle has occurred.  This
-- is the rd_ack output, and it makes it possible to do repeated reads from a
-- FIFO without doing writes.

-- The components that have been written for this application can be divided
-- into an output (control) chain and an input chain.

-- The output chain consists of:
-- - blockram32kx4byte -- internal SRAM to hold output specifications
-- - ccd_wpu -- CCD waveform processor

-- The input chain consist of:
-- - deserializer -- component that stores ADC data
-- - fifo_large -- FIFO storage for up to 64MB of ADC data

-- The fifo_large component accesses DDR2 RAM for backup storage.

-- The input and output chains are independent with the exception of two 
-- control lines from ccd_wpu to the deserializer.  The register file
-- controls the blockram, the FIFO, and the WPU.
------------------------------------------------------------------------------

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

-- This library provides the OBUFDS/IBUFDS components that can specify LVDS IO
Library UNISIM;
use UNISIM.vcomponents.all;

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
			mcb3_dram_dq     : inout  std_logic_vector(15 downto 0);
			mcb3_dram_a      : out std_logic_vector(14 downto 0) := (others => '0');
			mcb3_dram_ba     : out std_logic_vector(2 downto 0);
			mcb3_dram_ras_n  : out std_logic;
			mcb3_dram_cas_n  : out std_logic;
			mcb3_dram_we_n   : out std_logic;
			mcb3_dram_odt    : out std_logic;
			mcb3_dram_cke    : out std_logic;
			mcb3_dram_dm     : out std_logic;
			mcb3_dram_udqs   : inout  std_logic;
			mcb3_dram_udqs_n : inout  std_logic;
			mcb3_rzq         : inout  std_logic;
			mcb3_zio         : inout  std_logic;
			mcb3_dram_udm    : out std_logic;
			mcb3_dram_dqs    : inout  std_logic;
			mcb3_dram_dqs_n  : inout  std_logic;
			mcb3_dram_ck     : out std_logic;
			mcb3_dram_ck_n   : out std_logic;
			mcb3_odt	 : out std_logic;

			-- Clocks and misc
			clk_27mhz_1		: in std_logic;     
			clk_27mhz_2		: in std_logic;     
			pgood_1v2		: in std_logic;      
			pgood_1v8		: in std_logic;      
			pgood_3v3		: in std_logic;      
			port_output_en_n	: out std_logic; -- 0 to connect CN4 and CN9

			-- AT93C66 SPI EEPROM
			eeprom_cs	: out std_logic;       
			eeprom_sck	: out std_logic;      
			eeprom_si	: out std_logic;       
			eeprom_so	: in std_logic;  

			port0_p		: out std_logic_vector (11 downto 0);	
			port0_n		: out std_logic_vector (11 downto 0);	
			port1_p		: out std_logic_vector (11 downto 0);	
			port1_n		: out std_logic_vector (11 downto 0);	
			port2_p		: in std_logic_vector (19 downto 0);	
			port2_n		: in std_logic_vector (19 downto 0)	
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

			sys_clk_p   		: in  std_logic;
			sys_clk_n   		: in  std_logic;
			sys_reset_n 		: in  std_logic;
			
			-- Local Common
			clk                    : out std_logic;
			rst_n                  : out std_logic;
	
			--  Local Read Port
			rd_addr      : out std_logic_vector(10 downto 0);
			rd_be        : out std_logic_vector(3 downto 0);
			rd_data      : in  std_logic_vector(31 downto 0);
			rd_ack       : out std_logic;
                        
			--  Local Write Port
			wr_addr      : out std_logic_vector(10 downto 0);
			wr_be        : out std_logic_vector(7 downto 0);
			wr_data      : out std_logic_vector(31 downto 0);
			wr_en        : out std_logic;
			wr_busy      : in  std_logic	 
		);
	end component pcie_app_s6;
 
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
			mcb3_dram_dq         : inout  std_logic_vector(C3_NUM_DQ_PINS-1 downto 0);
			mcb3_dram_a          : out std_logic_vector(C3_MEM_ADDR_WIDTH-1 downto 0);
			mcb3_dram_ba         : out std_logic_vector(C3_MEM_BANKADDR_WIDTH-1 downto 0);
			mcb3_dram_ras_n      : out std_logic;
			mcb3_dram_cas_n      : out std_logic;
			mcb3_dram_we_n       : out std_logic;
			--mcb3_dram_odt        : out std_logic;
			mcb3_dram_cke        : out std_logic;
			mcb3_dram_dm         : out std_logic;
			mcb3_dram_udqs       : inout  std_logic;
			mcb3_dram_udqs_n     : inout  std_logic;
			mcb3_rzq             : inout  std_logic;
			mcb3_zio             : inout  std_logic;
			mcb3_dram_udm        : out std_logic;
			c3_sys_clk           : in  std_logic;
			c3_sys_rst_i         : in  std_logic;
			c3_calib_done        : out std_logic;
			c3_clk0              : out std_logic;
			c3_rst0              : out std_logic;
			mcb3_dram_dqs        : inout  std_logic;
			mcb3_dram_dqs_n      : inout  std_logic;
			mcb3_dram_ck         : out std_logic;
			mcb3_dram_ck_n       : out std_logic;
			c3_p0_cmd_clk        : in std_logic;
			c3_p0_cmd_en         : in std_logic;
			c3_p0_cmd_instr      : in std_logic_vector(2 downto 0);
			c3_p0_cmd_bl         : in std_logic_vector(5 downto 0);
			c3_p0_cmd_byte_addr  : in std_logic_vector(29 downto 0);
			c3_p0_cmd_empty      : out std_logic;
			c3_p0_cmd_full       : out std_logic;
			c3_p0_wr_clk         : in std_logic;
			c3_p0_wr_en          : in std_logic;
			c3_p0_wr_mask        : in std_logic_vector(C3_P0_MASK_SIZE - 1 downto 0);
			c3_p0_wr_data        : in std_logic_vector(C3_P0_DATA_PORT_SIZE - 1 downto 0);
			c3_p0_wr_full        : out std_logic;
			c3_p0_wr_empty       : out std_logic;
			c3_p0_wr_count       : out std_logic_vector(6 downto 0);
			c3_p0_wr_underrun    : out std_logic;
			c3_p0_wr_error       : out std_logic;
			c3_p0_rd_clk         : in std_logic;
			c3_p0_rd_en          : in std_logic;
			c3_p0_rd_data        : out std_logic_vector(C3_P0_DATA_PORT_SIZE - 1 downto 0);
			c3_p0_rd_full        : out std_logic;
			c3_p0_rd_empty       : out std_logic;
			c3_p0_rd_count       : out std_logic_vector(6 downto 0);
			c3_p0_rd_overflow    : out std_logic;
			c3_p0_rd_error       : out std_logic
		);
	end component;

	component pll1
		port(
			CLK_IN1           : in     std_logic;
			CLK_OUT1          : out    std_logic;
			CLK_OUT2          : out    std_logic;
			LOCKED            : out    std_logic
        	);
	end component;

	component pio_resynch is
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
	end component;

	component blockram_32kx4byte
		port (
			clka : in std_logic;
			wea : in std_logic_vector(0 downto 0);
			addra : in std_logic_vector(14 downto 0);
			dina : in std_logic_vector(31 downto 0);
			douta : out std_logic_vector(31 downto 0);
			clkb : in std_logic;
			web : in std_logic_vector(0 downto 0);
			addrb : in std_logic_vector(14 downto 0);
			dinb : in std_logic_vector(31 downto 0);
			doutb : out std_logic_vector(31 downto 0)
		);
	end component;

	component ccd_wpu is
		port (
			synch_i		: in  std_logic;
			clk_200mhz_i	: in  std_logic;
			rstn_i		: in  std_logic;

			sram_adr_o	: out std_logic_vector (17 downto 0);
			sram_dat_i	: in  std_logic_vector (31 downto 0);

			wpu_rst_i	: in  std_logic;
			start_i		: in  std_logic_vector (15 downto 0);
			stop_i		: in  std_logic_vector (15 downto 0);
			reps_i		: in  std_logic_vector (31 downto 0);
			reps_o		: out std_logic_vector (31 downto 0);

			waveform_o	: out std_logic_vector (15 downto 0);
                        active_o        : out std_logic;
			crcctl_o	: out std_logic
		);
	end component;

        component deserializer is
                port (
                        clk_i               : in  std_logic;
                        rstn_i              : in  std_logic;
                        clk_200mhz_i        : in  std_logic;

                        adc_miso_a_i        : in  std_logic;
                        adc_miso_b_i        : in  std_logic;
                        adc_sck_i           : in  std_logic;

                        sck_active_i        : in  std_logic;
                        crcctl_i            : in  std_logic;

                        ddr_wr_en_o         : out std_logic;
                        ddr_wr_data_o       : out std_logic_vector(31 downto 0);
                        test_pattern_i      : in  std_logic
                );
        end component;

	component fifo_large is
		port (
			clk_i               : in  std_logic;
			rstn_i              : in  std_logic;
			rd_rst_i            : in  std_logic;
			wr_rst_i            : in  std_logic;

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

			head_o              : out std_logic_vector(23 downto 0);
			tail_o              : out std_logic_vector(23 downto 0);

			ddr_req_o           : out std_logic;
			ddr_grant_i         : in  std_logic;

			wr_clk_i            : in std_logic;
			wr_data_count_o     : out std_logic_vector(9 downto 0);
			data_i              : in std_logic_vector(31 downto 0);
			wr_en_i             : in std_logic;
			full_o              : out std_logic;

			rd_clk_i            : in std_logic;
			rd_en_i             : in std_logic;
			data_o              : out std_logic_vector(31 downto 0);
			empty_o             : out std_logic;
			rd_data_count_o     : out std_logic_vector(9 downto 0)
		);
        end component;

	-- Local Common
	signal clk           : std_logic; -- 62.5MHz "user" clock from PCIe bridge
	signal rst_n         : std_logic; -- "user reset" associated with 62.5MHz
	signal clk_200mhz    : std_logic; -- actually 199.8 MHz (27*37/5)
	signal clk_77mhz     : std_logic; -- actually 76.846 MHz (27*37/13)
	signal rst77_n       : std_logic;
	signal pll_lock      : std_logic;
	signal lock_count    : unsigned(15 downto 0);
	signal synch_clk     : std_logic;
	signal synch_out     : std_logic;
	signal en_synch      : std_logic;
	signal en_synch_q    : std_logic;
	signal synch_count   : unsigned(5 downto 0);
	-- note: synch_out is sent to all 8 units.  When it comes back in, it
	-- is called synch_clk and is used to drive CCD waveform logic.

	--  Local Read Port
	signal rd_addr_62   : std_logic_vector(10 downto 0);
	signal rd_be_62     : std_logic_vector(3 downto 0);
	signal rd_data_62   : std_logic_vector(31 downto 0);
	signal rd_data      : std_logic_vector(31 downto 0);
	signal rd_ack_62    : std_logic;

	--  Local Write Port
	signal wr_addr_62   : std_logic_vector(10 downto 0);
	signal wr_be_62     : std_logic_vector(7 downto 0);
	signal wr_data_62   : std_logic_vector(31 downto 0);
	signal wr_en_62     : std_logic;
	signal wr_busy_62   : std_logic := '0';	 

	--  77MHz domain Write Port
	signal wr_addr      : std_logic_vector(10 downto 0);
	signal wr_be        : std_logic_vector(7 downto 0);
	signal wr_data      : std_logic_vector(31 downto 0);
	signal wr_en        : std_logic;
	
	-- DDR Interface Signals
	signal c3_calib_done		: std_logic;
	signal c3_p0_cmd_en		: std_logic;
	signal c3_p0_cmd_instr		: std_logic_vector (2 downto 0);
	signal c3_p0_cmd_bl		: std_logic_vector (5 downto 0);
	signal c3_p0_cmd_byte_addr	: std_logic_vector (29 downto 0);
	signal c3_p0_cmd_empty		: std_logic;
	signal c3_p0_cmd_full		: std_logic;
	signal c3_p0_wr_en		: std_logic;
	signal c3_p0_wr_data		: std_logic_vector (31 downto 0);
	signal c3_p0_wr_full		: std_logic;
	signal c3_p0_wr_empty		: std_logic;
	signal c3_p0_wr_count		: std_logic_vector(6 downto 0);
	signal c3_p0_wr_underrun	: std_logic;
	signal c3_p0_wr_error		: std_logic;
	signal c3_p0_rd_en		: std_logic;
	signal c3_p0_rd_data		: std_logic_vector (31 downto 0);
	signal c3_p0_rd_full		: std_logic;
	signal c3_p0_rd_empty		: std_logic;
	signal c3_p0_rd_count		: std_logic_vector(6 downto 0);
	signal c3_p0_rd_overflow	: std_logic;
	signal c3_p0_rd_error		: std_logic;

	signal rd_ack_q			: std_logic;
	signal wr_req			: std_logic;
	signal rd_req			: std_logic;
	signal rd_rst_q			: std_logic;
	signal rd_rst_q2		: std_logic;
	signal fifo_wr			: boolean;
	signal fifo_wr_q		: boolean;
	signal fifo_rd			: boolean;
	signal fifo_empty		: std_logic;
	signal fifo_data_i		: std_logic_vector(31 downto 0);
	signal fifo_data_o		: std_logic_vector(31 downto 0);
	signal fifo_count		: std_logic_vector(9 downto 0);

	signal adc_wr_en		: std_logic;
	signal adc_wr_data		: std_logic_vector (31 downto 0);

	-- IO signals
	-- these are single ended, connected directly to LVDS IO primitives
	signal lvds_cn4		: std_logic_vector (11 downto 0); -- 12 outs
	signal lvds_cn9		: std_logic_vector (11 downto 0); -- 12 outs
	signal lvds_cn8		: std_logic_vector (19 downto 0); -- 20 ins

	-- PFS FEE signals
	signal ccd_parallel_1		: std_logic;
	signal ccd_parallel_2		: std_logic;
	signal ccd_parallel_3		: std_logic;
	signal ccd_transfer_gate	: std_logic;
	signal ccd_serial_1		: std_logic;
	signal ccd_serial_2		: std_logic;
	signal ccd_reset_gate		: std_logic;
	signal ccd_summing_well		: std_logic;
	signal ccd_dc_restore		: std_logic;
	signal ccd_integrate_reset	: std_logic;
	signal ccd_integrate_minus	: std_logic;
	signal ccd_integrate_plus	: std_logic;
	signal ccd_adc_cnv		: std_logic;
	signal ccd_adc_sck		: std_logic;
	signal ccd_drain_gate		: std_logic;
	signal ccd_interrupt		: std_logic;

	signal ccd_adc_sck_ret		: std_logic;
	signal ccd_adc_miso_a		: std_logic;
	signal ccd_adc_miso_b		: std_logic;
	signal adc_sck_active		: std_logic;
	signal crcctl			: std_logic;

	signal ccd_waveform		: std_logic_vector (15 downto 0);

	signal sram_adr1		: std_logic_vector (17 downto 0);
	signal sram_dat1		: std_logic_vector (31 downto 0);
	signal br_we			: std_logic_vector (0 downto 0);
	signal wpu_start		: std_logic_vector (15 downto 0);
	signal wpu_stop			: std_logic_vector (15 downto 0);

	-- Register File
	constant REGISTER_COUNT		: natural := 32;
	type reg_32bit is record
		data		: std_logic_vector (31 downto 0);
		default		: std_logic_vector (31 downto 0);
		readonly	: boolean;
	end record;
	type reg_32bit_array	is array (natural range <>) of reg_32bit;
	signal register_file	: reg_32bit_array (REGISTER_COUNT-1 downto 0) := (others => (x"00000000", x"00000000", false));
	signal file_q		: reg_32bit_array (REGISTER_COUNT-1 downto 0) := (others => (x"00000000", x"00000000", false));
	signal file_q2		: reg_32bit_array (REGISTER_COUNT-1 downto 0) := (others => (x"00000000", x"00000000", false));
	
	-- Register Locations
	constant	R_ID		: natural := 16#0000#/4;
	constant	R_STATUS	: natural := 16#0004#/4;
	constant	R_EEPROM	: natural := 16#0008#/4;

	constant	R_DDR_RD_DATA	: natural := 16#0050#/4;
	constant	R_DDR_WR_DATA	: natural := 16#0054#/4;
	constant	R_DDR_COUNT	: natural := 16#0058#/4;
	constant	R_DDR_STATUS	: natural := 16#005C#/4;

	constant	R_HEAD		: natural := 16#0060#/4;
	constant	R_TAIL		: natural := 16#0064#/4;

	-- Custom registers:
	constant	R_BR_RD_DATA	: natural := 16#0010#/4;
	constant	R_BR_WR_DATA	: natural := 16#0014#/4;
	constant	R_BR_ADDR	: natural := 16#0018#/4;
	constant	R_WPU_CTRL	: natural := 16#0020#/4;
	constant	R_WPU_COUNT	: natural := 16#0024#/4;
	constant	R_WPU_START_STOP: natural := 16#0028#/4;
	constant	R_WPU_STATUS	: natural := 16#002C#/4;
	
	-- R_WPU_CTRL bits:
	-- bit 0: 1 = enable synchronization clock
	-- bit 1: 1 = hold WPU in reset
	-- bit 2: 1 = enable test pattern
	-- bit 3: 1 = reset read FIFO (software side)
	-- bit 4: 1 = reset write FIFO (FEE side)

begin

	port_output_en_n <= '0'; -- Enable I/O ports as soon as we are configured.

	-- PFS FEE signals
	-- This code is verbose for a reason.  It anticipates that pinouts will
	-- be changed based on physical cabling needs or convenience.  When
	-- pinouts change, just modify this section accordingly.
	lvds_cn4(6) 	<= ccd_parallel_1;
	lvds_cn4(8) 	<= ccd_parallel_2;
	lvds_cn4(9) 	<= ccd_parallel_3;
	lvds_cn4(7) 	<= ccd_transfer_gate;
	lvds_cn9(1) 	<= ccd_serial_1;
	lvds_cn4(1) 	<= ccd_serial_2;
	lvds_cn4(5) 	<= ccd_reset_gate;
	lvds_cn4(3) 	<= ccd_summing_well;
	lvds_cn4(10) 	<= ccd_dc_restore;
	lvds_cn9(0) 	<= ccd_integrate_reset;
	lvds_cn9(2) 	<= ccd_integrate_minus;
	lvds_cn9(3) 	<= ccd_integrate_plus;
	lvds_cn4(0) 	<= ccd_adc_cnv;
	lvds_cn4(2) 	<= ccd_adc_sck;
	lvds_cn4(11) 	<= ccd_drain_gate;
	lvds_cn4(4) 	<= ccd_interrupt;

	ccd_adc_sck_ret		<= lvds_cn8(16);
	-- ccd_adc_sck_ret		<= ccd_adc_sck; -- XXX testing only!!
	ccd_adc_miso_a		<= lvds_cn8(17);
	ccd_adc_miso_b		<= lvds_cn8(18);

	-- synchronization in and out
	-- synch_clk		<= lvds_cn8(15);
	synch_clk		<= synch_out; -- XXX testing only!!
	G_SYNCH: for i in 4 to 11 generate
		lvds_cn9(i) <= synch_out;
	end generate;
	
	-- CCD waveform designations
	-- These can also be changed, if BEE application software wants to
	-- change them for some reason.  However ccd_adc_sck gets special
	-- treatment and the WPU module assumes it is bit 13.  The other 15
	-- signals can be swapped around.
	ccd_parallel_1		<= ccd_waveform(0);
	ccd_parallel_2		<= ccd_waveform(1);
	ccd_parallel_3		<= ccd_waveform(2);
	ccd_transfer_gate	<= ccd_waveform(3);
	ccd_serial_1		<= ccd_waveform(4);
	ccd_serial_2		<= ccd_waveform(5);
	ccd_reset_gate		<= ccd_waveform(6);
	ccd_summing_well	<= ccd_waveform(7);
	ccd_dc_restore		<= ccd_waveform(8);
	ccd_integrate_reset	<= ccd_waveform(9);
	ccd_integrate_minus	<= ccd_waveform(10);
	ccd_integrate_plus	<= ccd_waveform(11);
	ccd_adc_cnv		<= ccd_waveform(12);
	ccd_adc_sck		<= ccd_waveform(13);
	ccd_drain_gate		<= ccd_waveform(14);
	ccd_interrupt		<= ccd_waveform(15);

	-----------------------------------------------------------------------
	-- PLL
	-----------------------------------------------------------------------
	-- Note: clk_200mhz is 199.8MHz. clk_77mhz is 76.846 MHz.
	pll_inst : pll1
		port map (
			CLK_IN1 => clk_27mhz_1,
			CLK_OUT1 => clk_200mhz,
			CLK_OUT2 => clk_77mhz,
			LOCKED => pll_lock
		);

	-- This mysterious block of code is a hack to create a reset signal
	-- that is synchronous to its clock.
	process (clk_77mhz)
	begin
		if rising_edge(clk_77mhz) then
			if (pll_lock = '1') then
				lock_count <= lock_count + 1;
			else
				lock_count <= x"0000";
				rst77_n <= '0';
			end if;	
			if (lock_count(15) = '1') then
				rst77_n <= '1';
			end if;
		end if;
	end process;

	-----------------------------------------------------------------------
	-- Waveform processing unit
	-----------------------------------------------------------------------
	register_file(R_WPU_STATUS).readonly 	<= true;
	wpu_start <= register_file(R_WPU_START_STOP).data(15 downto 0);
	wpu_stop  <= register_file(R_WPU_START_STOP).data(31 downto 16);
	wpu_inst : ccd_wpu
		port map (
			synch_i		=> synch_clk,
			clk_200mhz_i	=> clk_200mhz,
			rstn_i		=> rst77_n,

			sram_adr_o	=> sram_adr1,
			sram_dat_i	=> sram_dat1,

			wpu_rst_i	=> register_file(R_WPU_CTRL).data(1),
			start_i		=> wpu_start,
			stop_i		=> wpu_stop,
			reps_i		=> register_file(R_WPU_COUNT).data,
			reps_o		=> register_file(R_WPU_STATUS).default,

			waveform_o	=> ccd_waveform,
                        active_o        => adc_sck_active,
			crcctl_o        => crcctl
		);


	-----------------------------------------------------------------------
	-- Blockram to hold waveform data
	-----------------------------------------------------------------------
	-- At this time we have 128KB of SRAM, and the WPU thinks it can
	-- address 256KB.  sram_adr1(17) is ignored.
	register_file(R_BR_RD_DATA).readonly <= true;
	wpu_sram : blockram_32kx4byte
		port map (
			-- Port A is in the 62.5MHz domain and is accessed
			-- by the register block.
			clka	=> clk_77mhz,
			wea	=> br_we,
			addra	=> register_file(R_BR_ADDR).data(16 downto 2),
			dina	=> register_file(R_BR_WR_DATA).data,
			douta	=> register_file(R_BR_RD_DATA).default,

			-- Port B is in the synch_clk domain and is accessed
			-- by the WPU.
			clkb	=> synch_clk,
			web	=> "0", -- WPU does not write
			addrb	=> sram_adr1(16 downto 2),
			dinb	=> x"0000_0000", -- WPU does not write
			doutb	=> sram_dat1
		);
	
	-- Now that we have the pio_resynch mechanism, the br_we code has
	-- safely been simplified.  It could probably be further simplified.
	process (clk_77mhz, rst77_n)
	begin
		if rising_edge(clk_77mhz) then
			if (rst77_n = '0') then
				br_we <= "0";
			else
				br_we <= "0";
				if ((wr_en = '1') and (wr_addr =
				  STD_LOGIC_VECTOR(
				    TO_UNSIGNED(R_BR_WR_DATA,11)))) then
					br_we <= "1";
				end if;
			end if;
		end if;
	end process;

	-----------------------------------------------------------------------
	-- ADC data deserialization
	-----------------------------------------------------------------------

        des_core : deserializer
                port map (
                        -- clock and reset
                        clk_i              => clk_77mhz,
                        rstn_i              => rst77_n,
                        clk_200mhz_i        => clk_200mhz,

                        -- ADC lines from FEE
                        adc_miso_a_i        => ccd_adc_miso_a,
                        adc_miso_b_i        => ccd_adc_miso_b,
                        adc_sck_i           => ccd_adc_sck_ret,

                        -- active signal from CCD WPU indicates an ADC cycle
                        sck_active_i        => adc_sck_active,
                        crcctl_i            => crcctl,

                        -- DDR RAM interface
                        ddr_wr_en_o         => adc_wr_en,
                        ddr_wr_data_o       => adc_wr_data,
                        test_pattern_i      =>
                                register_file(R_WPU_CTRL).data(2)
                );

	-----------------------------------------------------------------------
	-- Image FIFO
	-----------------------------------------------------------------------
	image_fifo : fifo_large
		port map (
			clk_i               => clk_77mhz,
			rstn_i              => rst77_n,
			rd_rst_i            => 
                                register_file(R_WPU_CTRL).data(3),
			wr_rst_i            => 
                                register_file(R_WPU_CTRL).data(4),

			ddr_cmd_en_o        => c3_p0_cmd_en,
			ddr_cmd_instr_o     => c3_p0_cmd_instr,
			ddr_cmd_byte_addr_o => c3_p0_cmd_byte_addr,
			ddr_cmd_bl_o        => c3_p0_cmd_bl,
			ddr_cmd_empty_i     => c3_p0_cmd_empty,
			ddr_cmd_full_i      => c3_p0_cmd_full,
			ddr_wr_en_o         => c3_p0_wr_en,
			ddr_wr_data_o       => c3_p0_wr_data,
			ddr_wr_full_i       => c3_p0_wr_full,
			ddr_wr_empty_i      => c3_p0_wr_empty,
			ddr_rd_en_o         => c3_p0_rd_en,
			ddr_rd_data_i       => c3_p0_rd_data,
			ddr_rd_empty_i      => c3_p0_rd_empty,

			ddr_req_o           => open,
			ddr_grant_i         => '1', -- nobody else can use DDR

			-- These registers were just for debugging but I am
			-- leaving them connected for now:
			head_o              =>
				register_file(R_HEAD).default(23 downto 0),
			tail_o              =>
				register_file(R_TAIL).default(23 downto 0),

			wr_clk_i            => clk_77mhz,
			wr_data_count_o     => open, -- could monitor this
			data_i              => fifo_data_i,
			wr_en_i             => wr_req,
			full_o              => open, -- could monitor this

			rd_clk_i            => clk,
			rd_en_i             => rd_req,
			data_o              => fifo_data_o,
			empty_o             => fifo_empty,
			rd_data_count_o     => fifo_count
		);

	---------------------------------------------------------------------------
	-- Bus Interface
	---------------------------------------------------------------------------
	app : pcie_app_s6
		generic map (
			FAST_TRAIN 	=> FAST_TRAIN
		)
		port map (
			pci_exp_txp	=> pci_exp_txp,
			pci_exp_txn	=> pci_exp_txn,
			pci_exp_rxp	=> pci_exp_rxp,
			pci_exp_rxn	=> pci_exp_rxn,
			sys_clk_p	=> sys_clk_p,
			sys_clk_n	=> sys_clk_n, 
			sys_reset_n	=> sys_reset_n,

			-- Local Common
			clk		=> clk,   
			rst_n		=> rst_n, 	
			--  Local Read Port
			rd_addr		=> rd_addr_62,
			rd_be		=> rd_be_62,
			rd_data		=> rd_data_62,
			rd_ack		=> rd_ack_62,
			--  Local Write Port
			wr_addr		=> wr_addr_62,
			wr_be		=> wr_be_62,
			wr_data		=> wr_data_62,
			wr_en		=> wr_en_62,
			wr_busy		=> wr_busy_62
		);

	resynch_62_to77 : pio_resynch
		port map (
			-- Input clock and reset
			clk1_i      => clk,
			rstn1_i     => rst_n,
			-- Input signals
			wr_addr_i   => wr_addr_62,
			wr_be_i     => wr_be_62,
			wr_data_i   => wr_data_62,
			wr_en_i     => wr_en_62,
			-- Output clock and reset
			clk2_i      => clk_77mhz,
			rstn2_i     => rst77_n,
			-- Output signals
			wr_addr_o   => wr_addr,
			wr_be_o     => wr_be,
			wr_data_o   => wr_data,
			wr_en_o     => wr_en
		);

	-- The blocks of code below are the glue between the register file
	-- and the bus coming out of the PCIe PIO module.  Note that they are
	-- doing an endianness swap on the data lines, reversing the order of
	-- the bytes within a 32 bit word.  This is because while the x86 CPU
	-- is a little endian device, PCIe is a big endian bus.

	-- Register File Read
	process (file_q2, rd_addr_62, fifo_data_o, fifo_count)
	begin
		rd_data <= file_q2(TO_INTEGER(UNSIGNED(rd_addr_62))).data;
		-- Two read-only FIFO registers are not part of the register
		-- file, because they need to be in the 62.5MHz domain:
		if rd_addr_62 = STD_LOGIC_VECTOR(TO_UNSIGNED(R_DDR_RD_DATA,11)) then
			rd_data <= fifo_data_o;
		end if;
		if rd_addr_62 = STD_LOGIC_VECTOR(TO_UNSIGNED(R_DDR_COUNT,11)) then
			rd_data <= (others => '0');
			rd_data(9 downto 0) <= fifo_count;
		end if;
		-- Endian swap
		rd_data_62( 7 downto  0) <= rd_data(31 downto 24);
		rd_data_62(15 downto  8) <= rd_data(23 downto 16);
		rd_data_62(23 downto 16) <= rd_data(15 downto  8);
		rd_data_62(31 downto 24) <= rd_data( 7 downto  0);
	end process;
	
	-- Register File Resynchronize
	-- (should probably be implemented more carefully)
	G_REG_RESYNC: for i in 0 to REGISTER_COUNT-1 generate
		process (clk)
		begin
			if rising_edge (clk) then
				file_q(i).data <= register_file(i).data;
				file_q2(i).data <= file_q(i).data;
			end if;
		end process;
	end generate;

	-- Register File Write
	G_REG_WRITES: for i in 0 to REGISTER_COUNT-1 generate
		process (clk_77mhz, rst77_n)
		begin
			if rising_edge (clk_77mhz) then
				if ((rst77_n = '0') or register_file(i).readonly) then
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
	register_file(R_ID).default 	<= x"bee00064"; -- BEE board ID
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
	
	-----------------------------------------------------------------------
	-- IO connections
	-----------------------------------------------------------------------
	-- Port 0 -- 12 LVDS outputs on CN4
	G_PORT0: for i in 0 to 11 generate
		OBUFDS0_inst : OBUFDS
		generic map (
			IOSTANDARD => "default"
		)
		port map (
			O => port0_p(i),
			OB => port0_n(i),
			I => lvds_cn4(i)
		);
	end generate;
	
	-- Port 1 -- 12 LVDS outputs on CN9
	G_PORT1: for i in 0 to 11 generate
		OBUFDS1_inst : OBUFDS
		generic map (
			IOSTANDARD => "default"
		)
		port map (
			O => port1_p(i),
			OB => port1_n(i),
			I => lvds_cn9(i)
		);
	end generate;
	
	-- Port 2 -- 20 LVDS inputs on CN8
	G_PORT2: for i in 0 to 14 generate
		IBUFDS_inst : IBUFDS
		generic map (
			DIFF_TERM => TRUE, -- Differential Termination
			IBUF_LOW_PWR => FALSE, -- (high performance)
			IOSTANDARD => "default"
		)
		port map (
			O => lvds_cn8(i),
			I => port2_p(i),
			IB => port2_n(i)
		);
	end generate;

	-- 15 and 16 have to be IBUFGDS because they are clocks
	IBUFDS_15 : IBUFGDS
	generic map (
		DIFF_TERM => TRUE, -- Differential Termination
		IBUF_LOW_PWR => FALSE, -- (high performance)
		IOSTANDARD => "default"
	)
	port map (
		O => lvds_cn8(15),
		I => port2_p(15),
		IB => port2_n(15)
	);

	-- input 16 is the ADC SCK return.  If I want to use the falling edge
	-- instead of the rising edge I will swap _p and _n.
	-- Our design no longer treats this clock as a clock, but I think it
	-- is fine to leave it as IBUFGDS
	IBUFDS_16 : IBUFGDS
	generic map (
		DIFF_TERM => TRUE, -- Differential Termination
		IBUF_LOW_PWR => FALSE, -- (high performance)
		IOSTANDARD => "default"
	)
	port map (
		O => lvds_cn8(16),
		I => port2_p(16),
		IB => port2_n(16)
	);

	G_PORT3: for i in 17 to 19 generate
		IBUFDS_inst : IBUFDS
		generic map (
			DIFF_TERM => TRUE, -- Differential Termination
			IBUF_LOW_PWR => FALSE, -- (high performance)
			IOSTANDARD => "default"
		)
		port map (
			O => lvds_cn8(i),
			I => port2_p(i),
			IB => port2_n(i)
		);
	end generate;

	-----------------------------------------------------------------------
	-- 25MHz Synch_out clock generation
	-----------------------------------------------------------------------
	-- Note: en_synch is re-registered because we are crossing clock
	-- domains from 77MHz to 199.8MHz.  I believe the fact that I use a
	-- reset signal from the 77MHz domain for this 200MHz process is not
	-- a concern because when rst77_n is released, all these registers
	-- will be zero anyway.
	process (clk_200mhz, rst77_n)
	-- to-do: create a divisor register in case we want to run slower
	-- Currently, there is a constant divisor of 4 which creates 25MHz.
	begin
		if rising_edge(clk_200mhz) then
			if (rst77_n = '0') then
				en_synch <= '0';
				en_synch_q <= '0';
				synch_out <= '0';
				synch_count <= "000000";
			else
				en_synch <= register_file(R_WPU_CTRL).data(0);
				en_synch_q <= en_synch;
				synch_count <= synch_count + "1";
				if (synch_count = "000011") then
					synch_out <= en_synch_q and
						not synch_out;
					synch_count <= "000000";
				end if;
			end if;
		end if;
	end process;

	---------------------------------------------------------------------------
	-- Memory Interface
	---------------------------------------------------------------------------
	u_mig_39 : mig_39
		port map (

			c3_sys_clk		=> clk_77mhz,
			c3_sys_rst_i		=> rst77_n,

			-- Connections to DDR2 Chip
			mcb3_dram_dq		=> mcb3_dram_dq,
			mcb3_dram_a		=> mcb3_dram_a(12 downto 0),  
			mcb3_dram_ba		=> mcb3_dram_ba,
			mcb3_dram_ras_n		=> mcb3_dram_ras_n,
			mcb3_dram_cas_n		=> mcb3_dram_cas_n,
			mcb3_dram_we_n		=> mcb3_dram_we_n,
			--mcb3_dram_odt		=> mcb3_dram_odt,
			mcb3_dram_cke		=> mcb3_dram_cke,
			mcb3_dram_ck		=> mcb3_dram_ck,
			mcb3_dram_ck_n		=> mcb3_dram_ck_n,
			mcb3_dram_dqs		=> mcb3_dram_dqs,
			mcb3_dram_dqs_n		=> mcb3_dram_dqs_n,
			mcb3_dram_udqs		=> mcb3_dram_udqs,
			mcb3_dram_udqs_n 	=> mcb3_dram_udqs_n,
			mcb3_dram_udm 		=> mcb3_dram_udm,
			mcb3_dram_dm 		=> mcb3_dram_dm,
			mcb3_rzq        	=> mcb3_rzq,
			mcb3_zio        	=> mcb3_zio,

			c3_clk0			=> open, -- Output
			c3_rst0			=> open, -- Output

			c3_calib_done		=> c3_calib_done,

			c3_p0_cmd_clk		=> clk_77mhz,
			c3_p0_cmd_en		=> c3_p0_cmd_en,
			c3_p0_cmd_instr		=> c3_p0_cmd_instr, 
			c3_p0_cmd_bl		=> c3_p0_cmd_bl,
			c3_p0_cmd_byte_addr	=> c3_p0_cmd_byte_addr,
			c3_p0_cmd_empty		=> c3_p0_cmd_empty,
			c3_p0_cmd_full		=> c3_p0_cmd_full,
			c3_p0_wr_clk		=> clk_77mhz,
			c3_p0_wr_en		=> c3_p0_wr_en,
			c3_p0_wr_mask		=> "0000",
			c3_p0_wr_data		=> c3_p0_wr_data,
			c3_p0_wr_full		=> c3_p0_wr_full,
			c3_p0_wr_empty		=> c3_p0_wr_empty,
			c3_p0_wr_count		=> c3_p0_wr_count,
			c3_p0_wr_underrun	=> c3_p0_wr_underrun,
			c3_p0_wr_error		=> c3_p0_wr_error,
			c3_p0_rd_clk		=> clk_77mhz,
			c3_p0_rd_en		=> c3_p0_rd_en,
			c3_p0_rd_data		=> c3_p0_rd_data,
			c3_p0_rd_full		=> c3_p0_rd_full,
			c3_p0_rd_empty		=> c3_p0_rd_empty,
			c3_p0_rd_count		=> c3_p0_rd_count,
			c3_p0_rd_overflow	=> c3_p0_rd_overflow,
			c3_p0_rd_error		=> c3_p0_rd_error
		);

	register_file(R_DDR_RD_DATA).readonly <= true;
	register_file(R_DDR_COUNT).readonly <= true;
	register_file(R_DDR_STATUS).readonly  <= true;
	register_file(R_HEAD).readonly  <= true;
	register_file(R_TAIL).readonly  <= true;

	-----------------------------------------------------------------------
	-- We don't monitor this DDR information anymore, but there is no
	-- need to remove this code.
	register_file(R_DDR_STATUS).default(31)            <= c3_calib_done;
	register_file(R_DDR_STATUS).default(25)            <= c3_p0_cmd_empty;
	register_file(R_DDR_STATUS).default(24)            <= c3_p0_cmd_full;
	register_file(R_DDR_STATUS).default(7)             <= c3_p0_wr_full;
	register_file(R_DDR_STATUS).default(6)             <= c3_p0_wr_empty;
	register_file(R_DDR_STATUS).default(22 downto 16)  <= c3_p0_wr_count;
	register_file(R_DDR_STATUS).default(5)             <= c3_p0_wr_underrun;
	register_file(R_DDR_STATUS).default(4)             <= c3_p0_wr_error;
	register_file(R_DDR_STATUS).default(3)             <= c3_p0_rd_full;
	register_file(R_DDR_STATUS).default(2)             <= c3_p0_rd_empty;
	register_file(R_DDR_STATUS).default(14 downto 8)   <= c3_p0_rd_count;
	register_file(R_DDR_STATUS).default(1)             <= c3_p0_rd_overflow;
	register_file(R_DDR_STATUS).default(0)             <= c3_p0_rd_error;
	-----------------------------------------------------------------------

	-----------------------------------------------------------------------
	-- The boilerplate design provided by RTD had a clunky and broken
	-- mechanism for DDR access.  I have removed that and replaced it with
	-- a FIFO component.  The fifo_large component is a 32 bit wide FIFO
	-- that uses the DDR for extra storage.  It is the only DDR access
	-- mechanism in this design.  The register block can see how many
	-- data words are immediately available from this FIFO, and read them.
	-- The FIFO is normally written by the deserializer, but it can also
	-- be written by the register block for testing purposes.  Don't try
	-- to mix these.
	--
	-- Change with rev 0052: FIFO is writes are in the 77MHz domain but
	-- FIFO reads are in the 62MHz domain.
	-----------------------------------------------------------------------
	
	fifo_wr <= ((wr_en = '1') and
		(wr_addr = STD_LOGIC_VECTOR(TO_UNSIGNED(R_DDR_WR_DATA,11))));

	process (clk_77mhz, rst77_n)
	begin
	if rising_edge(clk_77mhz) then
		if (rst77_n = '0') then
			wr_req <= '0';
			fifo_data_i <= x"0000_0000";
			fifo_wr_q <= false;
		else
			wr_req <= '0';
			fifo_wr_q <= fifo_wr;
			------------------------------------------------------
			-- Writes are triggered by writing to R_DDR_WR_DATA
			------------------------------------------------------
			if (fifo_wr_q) then
				wr_req <= '1';
				fifo_data_i <=
					register_file(R_DDR_WR_DATA).data;
			end if;
			if (adc_wr_en = '1') then
				wr_req <= '1';
				fifo_data_i <= adc_wr_data;
			end if;
		end if;
	end if;
	end process;

	fifo_rd <= ((rd_ack_62 = '0') and (rd_ack_q = '1') and
		(rd_addr_62 = STD_LOGIC_VECTOR(TO_UNSIGNED(R_DDR_RD_DATA,11))));

	process (clk, rst_n)
	begin
	if rising_edge(clk) then
		if (rst_n = '0') then
			rd_req <= '0';
			rd_ack_q <= '0';
			rd_rst_q <= '0';
			rd_rst_q2 <= '0';
		else
			rd_req <= '0';
			rd_ack_q <= rd_ack_62;
			------------------------------------------------------
			-- Reads are triggered by reading from R_DDR_RD_DATA
			------------------------------------------------------
			if (fifo_rd) then
				rd_req <= '1';
			end if;
			------------------------------------------------------
			-- Below is a hack to empty the FIFO when the user 
			-- FIFO reset is asserted.  The same hack also exists
			-- inside fifo_large for the other sub-FIFO.  It would
			-- seem a lot cleaner if this little bit of logic was
			-- also encapsulated in fifo_large, but this was is
			-- convenient since that module has no internal 62.5MHz
			-- registers at this time.
			------------------------------------------------------
			rd_rst_q <= register_file(R_WPU_CTRL).data(3);
			rd_rst_q2 <= rd_rst_q;
                        if rd_rst_q2 = '1'
				and rd_req = '0'
				and fifo_empty = '0' then
				rd_req <= '1';
			end if;
		end if;
	end if;
	end process;

end rtl;
