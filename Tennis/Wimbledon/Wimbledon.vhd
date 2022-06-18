
library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity Wimbledon is
    Port ( rst_in : in STD_LOGIC;
			  clk_in : in  STD_LOGIC;
           data_in : in  STD_LOGIC;
           data_out : out  STD_LOGIC_VECTOR (7 downto 0);
			  debug_out : out STD_LOGIC
		  );
end Wimbledon;

architecture Behavioral of Wimbledon is
	COMPONENT bus_demuxer
		PORT (
			mux_rst_in: IN STD_LOGIC;
			mux_clk_in: IN STD_LOGIC;
			mux_data_in: IN STD_LOGIC;
			mux_data_out: OUT STD_LOGIC_VECTOR (7 downto 0);
			mux_debug_out: OUT STD_LOGIC
		);
		END COMPONENT;

begin
	inst_bus_demuxer: bus_demuxer PORT MAP(
		mux_rst_in => rst_in,
		mux_clk_in => clk_in,
		mux_data_in => data_in,
		mux_data_out => data_out,
		mux_debug_out => debug_out
		);
end Behavioral;

