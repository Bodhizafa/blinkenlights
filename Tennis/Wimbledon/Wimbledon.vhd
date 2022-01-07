----------------------------------------------------------------------------------
-- Company: 
-- Engineer: 
-- 
-- Create Date:    19:23:15 12/10/2021 
-- Design Name: 
-- Module Name:    Wimbledon - Behavioral 
-- Project Name: 
-- Target Devices: 
-- Tool versions: 
-- Description: 
--
-- Dependencies: 
--
-- Revision: 
-- Revision 0.01 - File Created
-- Additional Comments: 
--
----------------------------------------------------------------------------------
library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

-- Uncomment the following library declaration if using
-- arithmetic functions with Signed or Unsigned values
--use IEEE.NUMERIC_STD.ALL;

-- Uncomment the following library declaration if instantiating
-- any Xilinx primitives in this code.
--library UNISIM;
--use UNISIM.VComponents.all;

entity Wimbledon is
    Port ( rst_in : in STD_LOGIC;
			  clk_in : in  STD_LOGIC;
           data_in : in  STD_LOGIC;
           data_out : out  STD_LOGIC_VECTOR (7 downto 0)
		  );
end Wimbledon;

architecture Behavioral of Wimbledon is
	COMPONENT bus_demuxer
		PORT (
			mux_rst_in: IN STD_LOGIC;
			mux_clk_in: IN STD_LOGIC;
			mux_data_in: IN STD_LOGIC;
			mux_data_out: OUT STD_LOGIC_VECTOR (7 downto 0)
		);
		END COMPONENT;

begin
	inst_bus_demuxer: bus_demuxer PORT MAP(
		mux_rst_in => rst_in,
		mux_clk_in => clk_in,
		mux_data_in => data_in,
		mux_data_out => data_out
	);
end Behavioral;

