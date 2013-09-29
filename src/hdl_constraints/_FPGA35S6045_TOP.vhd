
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

-- This library provides the OBUFDS module that can specify LVDS IO
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
 
--	component PIO_EP_MEM_ACCESS is
--		port (
--			clk          : in  std_logic;
--			rst_n        : in  std_logic;
--
--			--  Read Port
--			rd_addr_i    : in  std_logic_vector(10 downto 0);
--			rd_be_i      : in  std_logic_vector(3 downto 0);
--			rd_data_o    : out std_logic_vector(31 downto 0);
--
--			--  Write Port
--			wr_addr_i    : in  std_logic_vector(10 downto 0);
--			wr_be_i      : in  std_logic_vector(7 downto 0);
--			wr_data_i    : in  std_logic_vector(31 downto 0);
--			wr_en_i      : in  std_logic;
--			wr_busy_o    : out std_logic
--		);
--	end component;

	component mig_39
	--component dp_mem_iface
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
			CLK_OUT1          : out    std_logic
        	);
	end component;

	component blockram_8kx4byte
		port (
			clka : in std_logic;
			wea : in std_logic_vector(0 downto 0);
			addra : in std_logic_vector(12 downto 0);
			dina : in std_logic_vector(31 downto 0);
			douta : out std_logic_vector(31 downto 0);
			clkb : in std_logic;
			web : in std_logic_vector(0 downto 0);
			addrb : in std_logic_vector(12 downto 0);
			dinb : in std_logic_vector(31 downto 0);
			doutb : out std_logic_vector(31 downto 0)
		);
	end component;

	component ccd_wpu is
		port (
			synch_i		: in  std_logic;
			clk_200mhz_i	: in  std_logic;
			rstn_i		: in  std_logic;

			sram_adr_o	: out std_logic_vector (15 downto 0);
			sram_dat_i	: in  std_logic_vector (31 downto 0);

			wpu_rst_i	: in  std_logic;
			len_i		: in  std_logic_vector (15 downto 0);
			reps_i		: in  std_logic_vector (31 downto 0);
			reps_o		: out std_logic_vector (31 downto 0);

			waveform_o	: out std_logic_vector (15 downto 0);
                        active_o        : out std_logic
		);
	end component;

        component deserializer is
                port (
                        clk_62mhz_i         : in  std_logic;
                        rstn_i              : in  std_logic;

                        adc_miso_a_i        : in  std_logic;
                        adc_miso_b_i        : in  std_logic;
                        adc_sck_i           : in  std_logic;

                        sck_active_i        : in  std_logic;

                        ddr_cmd_en_o        : out std_logic;
                        ddr_cmd_instr_o     : out std_logic_vector(2 downto 0);
                        ddr_cmd_byte_addr_o : out std_logic_vector(29 downto 0);
                        ddr_cmd_bl_o        : out std_logic_vector(5 downto 0);
                        ddr_cmd_empty_i     : in  std_logic;
                        ddr_cmd_full_i      : in  std_logic;
                        ddr_wr_en_o         : out std_logic;
                        ddr_wr_data_o       : out std_logic_vector(31 downto 0);
                        ddr_wr_full_i       : in  std_logic;

                        crc_o               : out std_logic_vector(15 downto 0);
                        crc_rst_i           : in  std_logic;

                        adr_rst_i           : in  std_logic
                );
        end component;

	-- Local Common
	signal clk           : std_logic;
	signal rst_n         : std_logic;
	signal clk_200mhz    : std_logic; -- actually 199.8 MHz (27*37/5)
	signal synch_clk     : std_logic;
	signal synch_out     : std_logic;
	signal en_synch      : std_logic;
	signal en_synch_q    : std_logic;
	signal synch_count   : unsigned(5 downto 0);
	-- note: synch_out is sent to all 8 units.  When it comes back in, it
	-- is called synch_clk and is used to drive CCD waveform logic.

	--  Local Read Port
	signal rd_addr      : std_logic_vector(10 downto 0);
	signal rd_be        : std_logic_vector(3 downto 0);
	signal rd_data      : std_logic_vector(31 downto 0);
	signal rd_ack       : std_logic;

	--  Local Write Port
	signal wr_addr      : std_logic_vector(10 downto 0);
	signal wr_be        : std_logic_vector(7 downto 0);
	signal wr_data      : std_logic_vector(31 downto 0);
	signal wr_en        : std_logic;
	signal wr_busy      : std_logic := '0';	 
	
	-- DDR Interface Signals
	signal ddr_data_wr		: std_logic;
	signal ddr_data_wr_d		: std_logic;
	signal ddr_data_wr_d1		: std_logic;
	signal ddr_data_rd		: std_logic;
	signal ddr_data_rd_d		: std_logic;
	signal c3_p0_cmd_instr		: std_logic_vector (2 downto 0);
	signal c3_p0_cmd_en		: std_logic;
	signal c3_p0_cmd_bl		: std_logic_vector (5 downto 0);
	signal c3_p0_cmd_byte_addr	: std_logic_vector (29 downto 0);
	signal c3_p0_rd_en		: std_logic;
	signal c3_p0_wr_en		: std_logic;
	signal c3_p0_wr_data		: std_logic_vector (31 downto 0);
	signal cmd_delay		: std_logic;	
	signal cmd_delay2		: std_logic;	

	signal wr_req			: std_logic;
	signal cmd_req			: std_logic;
	signal pio_cmd_instr            : std_logic_vector (2 downto 0);
	signal pio_cmd_bl               : std_logic_vector (5 downto 0);
	signal pio_cmd_byte_addr        : std_logic_vector (29 downto 0);

	signal adc_cmd_en		: std_logic;
	signal adc_cmd_instr		: std_logic_vector (2 downto 0);
	signal adc_cmd_bl		: std_logic_vector (5 downto 0);
	signal adc_cmd_byte_addr	: std_logic_vector (29 downto 0);
	signal adc_cmd_empty		: std_logic;
	signal adc_cmd_full		: std_logic;
	signal adc_wr_en		: std_logic;
	signal adc_wr_data		: std_logic_vector (31 downto 0);
	signal adc_wr_full		: std_logic;
	signal adc_wr_empty		: std_logic;
	signal adc_wr_count		: std_logic_vector (6 downto 0);
	signal adc_wr_underrun		: std_logic;
	signal adc_wr_error		: std_logic;

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

	signal ccd_waveform		: std_logic_vector (15 downto 0);

	signal sram_adr1		: std_logic_vector (15 downto 0);
	signal sram_dat1		: std_logic_vector (31 downto 0);
	signal br_we			: std_logic_vector (2 downto 0);
	signal len			: std_logic_vector (15 downto 0);

	-- Register File
	constant REGISTER_COUNT		: natural := 32;
	type reg_32bit is record
		data		: std_logic_vector (31 downto 0);
		default		: std_logic_vector (31 downto 0);
		readonly	: boolean;
	end record;
	type reg_32bit_array	is array (natural range <>) of reg_32bit;
	signal register_file	: reg_32bit_array (REGISTER_COUNT-1 downto 0) := (others => (x"00000000", x"00000000", false));
	
	-- Register Locations
	constant	R_ID		: natural := 16#0000#/4;
	constant	R_STATUS	: natural := 16#0004#/4;
	constant	R_EEPROM	: natural := 16#0008#/4;

	constant	R_DDR_RD_DATA	: natural := 16#0050#/4;
	constant	R_DDR_WR_DATA	: natural := 16#0054#/4;
	constant	R_DDR_ADDR	: natural := 16#0058#/4;
	constant	R_DDR_STATUS	: natural := 16#005C#/4;
	constant	R_DDR_CMD	: natural := 16#0060#/4;

	-- Custom registers:
	constant	R_BR_RD_DATA	: natural := 16#0010#/4;
	constant	R_BR_WR_DATA	: natural := 16#0014#/4;
	constant	R_BR_ADDR	: natural := 16#0018#/4;
	constant	R_WPU_CTRL	: natural := 16#0020#/4;
	constant	R_WPU_COUNT	: natural := 16#0024#/4;
	constant	R_WPU_LEN	: natural := 16#0028#/4;
	constant	R_WPU_STATUS	: natural := 16#002C#/4;
	constant	R_IMAGE_ADR	: natural := 16#0030#/4;
	constant	R_CRC   	: natural := 16#0034#/4;

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

	--ccd_adc_sck_ret		<= lvds_cn8(16);
	ccd_adc_sck_ret		<= ccd_adc_sck; -- XXX testing only!!
	ccd_adc_miso_a		<= lvds_cn8(17);
	ccd_adc_miso_b		<= lvds_cn8(18);

	-- synchronization in and out
	--synch_clk		<= lvds_cn8(15);
	synch_clk <= synch_out; -- XXX testing only!!
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
	-- Note: The specification is for all CCD timing to be based on a
	-- 50MHz clock.  Unfortunately we cannot generate 50MHz exactly, or
	-- multiples of it, using a 27MHz input.  There may be a way to do that
	-- but if so it is not immediately clear.  At this time we are
	-- generating 199.8MHz and calling it 200.  As a result all our timing
	-- is 0.1% slower than specified, and our 50MHz ADC clock is actually
	-- 49.95MHz.

	-- It may be that the chip actually has multiple PLLs that I can 
	-- string together to get what I want, and the wizard just doesn't
	-- know how to do that.  I can experiment more later if needed.
	pll_inst : pll1
		port map (
			CLK_IN1 => clk_27mhz_1,
			CLK_OUT1 => clk_200mhz
		);

	-----------------------------------------------------------------------
	-- Waveform processing unit
	-----------------------------------------------------------------------
	register_file(R_WPU_STATUS).readonly 	<= true;
	len <= register_file(R_WPU_LEN).data(15 downto 0);
	wpu_inst : ccd_wpu
		port map (
			synch_i		=> synch_clk,
			clk_200mhz_i	=> clk_200mhz,
			rstn_i		=> rst_n,

			sram_adr_o	=> sram_adr1,
			sram_dat_i	=> sram_dat1,

			wpu_rst_i	=> register_file(R_WPU_CTRL).data(1),
			len_i		=> len,
			reps_i		=> register_file(R_WPU_COUNT).data,
			reps_o		=> register_file(R_WPU_STATUS).default,

			waveform_o	=> ccd_waveform,
                        active_o        => adc_sck_active
		);


	-----------------------------------------------------------------------
	-- Blockram to hold waveform data
	-----------------------------------------------------------------------
	register_file(R_BR_RD_DATA).readonly <= true;
	wpu_sram : blockram_8kx4byte
		port map (
			-- Port A is in the 62.5MHz domain and is accessed
			-- by the register block.
			clka	=> clk,
			wea	=> br_we(2 downto 2),
			addra	=> register_file(R_BR_ADDR).data(14 downto 2),
			dina	=> register_file(R_BR_WR_DATA).data,
			douta	=> register_file(R_BR_RD_DATA).default,

			-- Port B is in the synch_clk domain and is accessed
			-- by the WPU.
			clkb	=> synch_clk,
			web	=> "0", -- WPU does not write
			addrb	=> sram_adr1(14 downto 2),
			dinb	=> x"0000_0000", -- WPU does not write
			doutb	=> sram_dat1
		);
	
	-- The following process block is a long winded way of saying
	-- the following:
	-- Any time a write is observed to the blockram write data register,
	-- wait 2 clock cycles and then assert the blockram write enable.
	--
	-- br_we is 3 bits because it is a 3 bit FIFO and only the the 3rd bit
	-- is used.  This FIFO mechanism is probably not even needed, but it
	-- doesn't do any harm because PCIe writes will come through very 
	-- slowly anyway.
	process (clk, rst_n)
	begin
		if rising_edge(clk) then
			if (rst_n = '0') then
				br_we <= "000";
			else
				br_we(2) <= br_we(1);
				br_we(1) <= br_we(0);
				if ((wr_en = '1') and (wr_addr =
				  STD_LOGIC_VECTOR(
				    TO_UNSIGNED(R_BR_WR_DATA,11)))) then
					br_we(0) <= '1';
				else
					br_we(0) <= '0';
				end if;
			end if;
		end if;
	end process;

	-----------------------------------------------------------------------
	-- ADC data deserialization
	-----------------------------------------------------------------------

        -- For now, the CRC is reset any time the WPU is reset.
	register_file(R_CRC).readonly <= true;
	register_file(R_IMAGE_ADR).readonly <= true;
	register_file(R_IMAGE_ADR).default(29 downto 0) <= adc_cmd_byte_addr;
        des_core : deserializer
                port map (
                        -- clock and reset
                        clk_62mhz_i         => clk,
                        rstn_i              => rst_n,

                        -- ADC lines from FEE
                        adc_miso_a_i        => ccd_adc_miso_a,
                        adc_miso_b_i        => ccd_adc_miso_b,
                        adc_sck_i           => ccd_adc_sck_ret,

                        -- active signal from CCD WPU indicates an ADC cycle
                        sck_active_i        => adc_sck_active,

                        -- DDR RAM interface
                        ddr_cmd_en_o        => adc_cmd_en,
                        ddr_cmd_instr_o     => adc_cmd_instr,
                        ddr_cmd_byte_addr_o => adc_cmd_byte_addr,
                        ddr_cmd_bl_o        => adc_cmd_bl,
                        ddr_cmd_empty_i     => adc_cmd_empty,
                        ddr_cmd_full_i      => adc_cmd_full,
                        ddr_wr_en_o         => adc_wr_en,
                        ddr_wr_data_o       => adc_wr_data,
                        ddr_wr_full_i       => adc_wr_full,

                        -- CRC output
                        crc_o               =>
                                register_file(R_CRC).default(15 downto 0),
                        crc_rst_i           =>
			        register_file(R_WPU_CTRL).data(1),
                        adr_rst_i           =>
			        register_file(R_WPU_CTRL).data(2)
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
			clk                 => clk,   
			rst_n               => rst_n, 	
			--  Local Read Port
			rd_addr		=> rd_addr,
			rd_be		=> rd_be,  
			rd_data		=> rd_data,
			rd_ack		=> rd_ack,
			--  Local Write Port
			wr_addr             => wr_addr,
			wr_be               => wr_be,  
			wr_data             => wr_data,
			wr_en               => wr_en,  
			wr_busy             => wr_busy
		);

	-- The blocks of code below are the glue between the register file
	-- and the bus coming out of the PCIe PIO module.  Note that they are
	-- doing an endianness swap on the data lines, reversing the order of
	-- the bytes within a 32 bit word.  This is because while the x86 CPU
	-- is a little endian device, PCIe is a big endian bus.

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
	register_file(R_ID).default 	<= x"bee00015"; -- BEE board ID
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
	G_PORT2: for i in 0 to 19 generate
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
	-- domains from 62.5MHz to 199.8MHz.
	process (clk_200mhz, rst_n)
	-- to-do: create a divisor register in case we want to run slower
	-- Currently, there is a constant divisor of 4 which creates 25MHz.
	begin
		if rising_edge(clk_200mhz) then
			if (rst_n = '0') then
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
	--u_mig_39 : dp_mem_iface
		port map (

			c3_sys_clk		=> clk,
			c3_sys_rst_i		=> rst_n,

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

			c3_calib_done		=>
				register_file(R_DDR_STATUS).default(31),

			c3_p0_cmd_clk		=> clk,
			c3_p0_cmd_en		=> c3_p0_cmd_en,
			c3_p0_cmd_instr		=> c3_p0_cmd_instr, 
			c3_p0_cmd_bl		=> c3_p0_cmd_bl,
			c3_p0_cmd_byte_addr	=> c3_p0_cmd_byte_addr,
			c3_p0_cmd_empty		=>
				register_file(R_DDR_STATUS).default(25),
			c3_p0_cmd_full		=>
				register_file(R_DDR_STATUS).default(24),
			c3_p0_wr_clk		=> clk,
			c3_p0_wr_en		=> c3_p0_wr_en,
			c3_p0_wr_mask		=> "0000",
			c3_p0_wr_data		=> c3_p0_wr_data,
			c3_p0_wr_full		=>
				register_file(R_DDR_STATUS).default(7),
			c3_p0_wr_empty		=>
				register_file(R_DDR_STATUS).default(6),
			c3_p0_wr_count		=>
				register_file(R_DDR_STATUS).default(22 downto 16),
			c3_p0_wr_underrun	=>
				register_file(R_DDR_STATUS).default(5),
			c3_p0_wr_error		=> register_file(R_DDR_STATUS).default(4),
			c3_p0_rd_clk		=> clk,
			c3_p0_rd_en		=> c3_p0_rd_en,
			c3_p0_rd_data		=>
				register_file(R_DDR_RD_DATA).default,
			c3_p0_rd_full		=>
				register_file(R_DDR_STATUS).default(3),
			c3_p0_rd_empty		=>
				register_file(R_DDR_STATUS).default(2),
			c3_p0_rd_count		=>
				register_file(R_DDR_STATUS).default(14 downto 8),
			c3_p0_rd_overflow	=>
				register_file(R_DDR_STATUS).default(1),
			c3_p0_rd_error		=>
				register_file(R_DDR_STATUS).default(0)
		);

	register_file(R_DDR_RD_DATA).readonly <= true;
	register_file(R_DDR_STATUS).readonly  <= true;

	-----------------------------------------------------------------------
	-- The PIO/register_file design provided here by Xilinx and RTD is
	-- really not very useful.  It is not a real bus; it acts like all
	-- registers in the FPGA are essentially SRAM that can have its data
	-- ready for a read in one clock cycle.  The weakness of this becomes
	-- apparent when you try to connect it to the memory interface, where
	-- reads take an arbitrary amount of time.  RTD tried to hack their
	-- way around this by having reads triggered by writes to the address
	-- register.  There were also some bugs in how they did that.  Even
	-- with the bugs fixed, it did not work well because it can take a long
	-- time between when you request a read and when the MCB completes it.
	--
	-- So, I have installed a modified method that requires software to
	-- have more knowledge of the memory interface and direct control of
	-- it.  Now commands have to be sent to the command interface, and
	-- writes and reads to the data registers cause writes and reads to
	-- the RAM FIFOs.  In order to detect reads, I had to add the rd_ack
	-- port to the PCIe core.  I found out only through experimentation
	-- that this signal is high for 2 clocks when there is a read.  This is
	-- why the code below says:
	-- 	c3_p0_rd_en <= not c3_p0_rd_en;
	-- instead of just
	-- 	c3_p0_rd_en <= '1';
	--
	-- This new method allows for bursts inside the FPGA, but each read or
	-- write is still a single 32 bit PCIe read or write, so performance
	-- is still terrible.  Writing and reading back 128MB takes over 4
	-- minutes.  We have about 1MB/s bandwidth on a 2.5GHz link.
	-----------------------------------------------------------------------
	
	pio_cmd_byte_addr <= register_file(R_DDR_ADDR).data(29 downto 0);
	pio_cmd_bl <= register_file(R_DDR_CMD).data(5 downto 0);
	pio_cmd_instr <= register_file(R_DDR_CMD).data(10 downto 8);

	process (clk, rst_n)
	begin
		if rising_edge(clk) then
			if (rst_n = '0') then
				wr_req <= '0';
				cmd_req <= '0';
				c3_p0_cmd_en <= '0';
				c3_p0_cmd_bl <= "000000";
				c3_p0_cmd_instr <= "000";
				c3_p0_cmd_byte_addr <= (others => '0');
				c3_p0_wr_en <= '0';
				c3_p0_rd_en <= '0';
				c3_p0_wr_data <= (others => '0');
			else
				------------------------------------------------
				-- Writes are triggered by writing to the
				-- WR_DATA register
				------------------------------------------------
				if ((wr_en = '1') and (wr_addr = STD_LOGIC_VECTOR(TO_UNSIGNED(R_DDR_WR_DATA,11)))) then
					wr_req <= '1';
				end if;

				------------------------------------------------
				-- Reads are triggered by reading from the
				-- RD_DATA register
				------------------------------------------------
				c3_p0_rd_en <= '0';
				if ((rd_ack = '1') and (rd_addr = STD_LOGIC_VECTOR(TO_UNSIGNED(R_DDR_RD_DATA,11)))) then
					if (register_file(R_DDR_STATUS).default(2) = '0') then
						c3_p0_rd_en <= not c3_p0_rd_en;
					end if;
				end if;
				
				------------------------------------------------
				-- Commands are triggered by writing to the
				-- ADDR register
				------------------------------------------------
				if ((wr_en = '1') and (wr_addr = STD_LOGIC_VECTOR(TO_UNSIGNED(R_DDR_ADDR,11)))) then
					cmd_req <= '1';
				end if;
				
				------------------------------------------------
				-- Issue write to MCB
				------------------------------------------------
				c3_p0_wr_en <= '0';
				if (adc_wr_en = '1') then
					c3_p0_wr_en <= '1';
					c3_p0_wr_data <= adc_wr_data;
				elsif (wr_req = '1') then
					c3_p0_wr_en <= '1';
					c3_p0_wr_data <=
					  register_file(R_DDR_WR_DATA).data;
					wr_req <= '0';
				end if;

				------------------------------------------------
				-- Issue command to MCB
				------------------------------------------------
				c3_p0_cmd_en <= '0';
				if (adc_cmd_en = '1') then
					c3_p0_cmd_en <= '1';
					c3_p0_cmd_bl <= adc_cmd_bl;
					c3_p0_cmd_instr <= adc_cmd_instr;
					c3_p0_cmd_byte_addr <=
						adc_cmd_byte_addr;
				elsif (cmd_req = '1') then
					c3_p0_cmd_en <= '1';
					c3_p0_cmd_bl <= pio_cmd_bl;
					c3_p0_cmd_instr <= pio_cmd_instr;
					c3_p0_cmd_byte_addr <=
						pio_cmd_byte_addr;
					cmd_req <= '0';
				end if;
			end if;

		end if;
	end process;
	
end rtl;
