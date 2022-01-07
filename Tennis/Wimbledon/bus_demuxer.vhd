library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity bus_demuxer is
    Port (mux_rst_in: in STD_LOGIC;
			 mux_clk_in : in  STD_LOGIC;
          mux_data_in : in  STD_LOGIC;
          mux_data_out : out  STD_LOGIC_VECTOR (7 downto 0));
end bus_demuxer;

architecture Behavioral of bus_demuxer is	
	signal counter: natural range 0 to 7;
	signal shift_buf: std_logic_vector(7 downto 0);
	signal leadin_active: std_logic;
	type t_state is (PRE_LEADIN, LEADIN, RUNNING, STARTING);
	signal state: t_state;
begin
	process (mux_clk_in, mux_rst_in)
	begin
		if mux_rst_in = '0' then
			counter <= 0;
			shift_buf <= x"00";
			mux_data_out <= x"00";
			state <= PRE_LEADIN;
		elsif RISING_EDGE(mux_clk_in) then
			case state is 
				when PRE_LEADIN =>
					mux_data_out <= x"00";
					shift_buf <= x"00";
					if mux_data_in = '1' then
						state <= LEADIN;
						counter <= 1;
					else
						counter <= 0;
					end if; 
				when LEADIN =>
					counter <= (counter + 1) mod 8;
					if mux_data_in = '1' then
						if counter = 7 then
							state <= STARTING;
							counter <= 0;
						end if;
					else
						state <= PRE_LEADIN;
						counter <= 0;
					end if; 
				when STARTING => 
					counter <= (counter + 1) mod 8;
					shift_buf(7 - counter) <= mux_data_in; -- MSB comes out first
					mux_data_out <= std_logic_vector(shift_left(to_unsigned(2#11000000#, 8), 1 - counter));
					if counter = 1 then
						state <= RUNNING;
					end if;
				when RUNNING => 
					counter <= (counter + 1) mod 8;
					shift_buf(7 - counter) <= mux_data_in; -- MSB comes out first
					mux_data_out <= (shift_buf and std_logic_vector(rotate_right(to_unsigned(2#00000110#, 8), counter))) or
						std_logic_vector(rotate_right(to_unsigned(2#10000001#, 8), counter));
			end case;
		end if;
	end process;
end Behavioral;

