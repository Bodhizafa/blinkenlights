LIBRARY ieee;
USE ieee.std_logic_1164.all;
USE ieee.std_logic_unsigned.all;
USE ieee.numeric_std.all;
LIBRARY std;
USE std.textio.all;
 
-- Uncomment the following library declaration if using
-- arithmetic functions with Signed or Unsigned values
--USE ieee.numeric_std.ALL;
 
ENTITY wimbledon_tb IS
END wimbledon_tb;
 
ARCHITECTURE behavior OF wimbledon_tb IS 
 
    -- Component Declaration for the Unit Under Test (UUT)
 
    COMPONENT Wimbledon
    PORT(
	    rst_in : IN std_logic;
       clk_in : IN  std_logic;
       data_in : IN  std_logic;
       data_out : OUT  std_logic_vector(7 downto 0)
        );
    END COMPONENT;


   --Inputs
	signal rst_in: std_logic := '0';
   signal clk_in : std_logic := '0';
   signal data_in : std_logic := '0';
 	--Outputs
   signal data_out : std_logic_vector(7 downto 0);

   -- Clock period definitions
   constant clk_in_period : time := 100 ns; -- 150
	constant data_len: INTEGER := 32;

BEGIN
 
	-- Instantiate the Unit Under Test (UUT)
   uut: Wimbledon PORT MAP (
			rst_in => rst_in,
         clk_in => clk_in,
         data_in => data_in,
         data_out => data_out
		);

   -- Clock process definitions
   clk_in_process :process
   begin
		clk_in <= '0';
		wait for clk_in_period/2;
		clk_in <= '1';
		wait for clk_in_period/2;
   end process;
 

   -- Stimulus process
   stim_proc: process
		TYPE t_char_file IS FILE OF character;
		file in_file : t_char_file OPEN READ_MODE is "input1.bin";
		variable char_buffer: character;
		variable cur_byte : std_logic_vector(7 downto 0);
   begin		
      -- reset
      wait for clk_in_period * 1;	
		rst_in <= '1';
		while not endfile(in_file) loop
			read(in_file, char_buffer);
			cur_byte := std_logic_vector(to_unsigned(character'POS(char_buffer), 8));
			for i in 7 downto 0 loop
				wait until FALLING_EDGE(clk_in);
				data_in <= cur_byte(i);
				
				--report "Char: " & " #" & std_logic'image(cur_byte(i)) & " " & integer'image(i);
			end loop;
		end loop;
		report "Finished";
		file_close(in_file);
		rst_in <= '0';
      wait;
   end process;

END;
