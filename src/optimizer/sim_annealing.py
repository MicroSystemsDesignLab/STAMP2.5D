import random, os, math
import numpy as np
import config
import block_occupation
import routing
from copy import deepcopy

######################Remote Connection Code
from thermal_connector import thermal_mechanical_stress
##########################


def boundary_check(system, x, y, w, h): #####Equation 11 in paper
	# w and h here includes microbump overhead
	if (x - w / 2) < 0:
		return False
	if (x + w / 2) > system.intp_size:
		return False
	if (y - h / 2) < 0:
		return False
	if (y + h / 2) > system.intp_size:
		return False
	return True

def close_neighbor(system, grid):
	''' slightly moving chiplets, do not consider rotation'''
	chiplet_order = np.random.permutation(range(system.chiplet_count))
	granularity = system.granularity
	for p in chiplet_order:
		direction_order = np.random.permutation(['up', 'down', 'left', 'right'])
		xx, yy, width, height = system.x[p], system.y[p], system.width[p] + 2 * system.hubump[p], system.height[p] + 2 * system.hubump[p]
		# print ('chiplet ', p + 2)
		for d in direction_order:
			# print (d)
			# re-connect the direction with the appropriate function in order to easily visulize using print-grid(). The dirctions are referring to the grid printed on screen, the directions in functions are referring to conventional x-y coordinates, origin in the left-bottom corner.
			if d == 'left':
				if block_occupation.check_down_occupation(grid, granularity, xx, yy - granularity, width, height):
					# print ('chiplet', p + 2, d)
					return p, xx, yy - granularity
			elif (d == 'right') and (yy + granularity <= system.intp_size):
				if block_occupation.check_up_occupation(grid, granularity, xx, yy + granularity, width, height):
					# print ('chiplet', p + 2, d)
					return p, xx, yy + granularity
			elif d == 'up':
				if block_occupation.check_left_occupation(grid, granularity, xx - granularity, yy, width, height):
					# print ('chiplet', p + 2, d)
					return p, xx - granularity, yy
			elif (d == 'down') and (xx + granularity <= system.intp_size):
				if block_occupation.check_right_occupation(grid, granularity, xx + granularity, yy, width, height):
					# print ('chiplet', p + 2, d)
					return p, xx + granularity, yy
	print ('No chiplet can be moved.')
	exit()

def jumping_neighbor(system, grid):
	'''define a neighbor placement as move one chiplet to anywhere can be located. 
	rotate if needed. We do not consider swapping, since can't gaurantee the placement
	is still legal (no overlap) after swapping'''

	n = system.chiplet_count
	granularity = system.granularity
	count = 0
	while True:
		pick_chiplet = random.randint(0, n - 1)
		x_new = random.randint(1, system.intp_size / granularity - 1) * granularity
		y_new = random.randint(1, system.intp_size / granularity - 1) * granularity
		rotation = random.randint(0,1)
		if rotation == 1:
			chiplet_width, chiplet_height = system.height[pick_chiplet], system.width[pick_chiplet]
		else:
			chiplet_height, chiplet_width = system.height[pick_chiplet], system.width[pick_chiplet]			
		if boundary_check(system, x_new, y_new, chiplet_width + 2 * system.hubump[pick_chiplet], chiplet_height + 2 * system.hubump[pick_chiplet]) and block_occupation.replace_block_occupation(grid, granularity, x_new, y_new, chiplet_width + 2 * system.hubump[pick_chiplet], chiplet_height + 2 * system.hubump[pick_chiplet], pick_chiplet):
			print ('found a random placement at', count, 'th trial')
			break
		count += 1
		if count > 10000:
			# it's not easy to find a legal placement using random method. try move each chiplet (in random order) slightly until find a legal solution
			print ('cannot find a legal random placement, go with close_neighbor')
			return close_neighbor(system, grid)
	return pick_chiplet, x_new, y_new, rotation

def accept_probability(old_temp, new_temp, old_length, new_length, T, weight, old_stress, new_stress):
	weight = 'adpTWS'
	max_allowable_stress= 400
	# Compute stress weight c as before.
	c = min(0.1 + (max(old_stress, new_stress) / max_allowable_stress) ** 1.5 * 0.5, 0.9)
	# Force b + c = 1
	b = 1 - c

	# Then define the cost function directly:
	if length_min != length_max and stress_min != stress_max:
		old_cost = b * (old_length - length_min) / (length_max - length_min) + c * (old_stress - stress_min) / (stress_max - stress_min)
		new_cost = b * (new_length - length_min) / (length_max - length_min) + c * (new_stress - stress_min) / (stress_max - stress_min)
	else:
		old_cost = b * (old_length - length_min) + c * (old_stress - stress_min)
		new_cost = b * (new_length - length_min) + c * (new_stress - stress_min)

	print("b,c: ",b,c)  

	delta = - (new_cost - old_cost)
	if delta > 0:
		ap = 1
	else:
		ap = math.exp( delta / T )
	# print (old_temp, new_temp, old_length, new_length, T, delta, ap)
	return ap, b, c

# def accept_probability(old_temp, new_temp, T):
# 	delta = (old_temp - new_temp)
# 	# print (old_temp, new_temp, T, delta)
# 	if delta > 0:
# 		ap = 1
# 	else:
# 		ap = math.exp( delta / T )
# 	return ap

def update_minmax(temp, length, stress): ###############~~~~~~~~~Updated this to include stress~~~~~~~~~~~~~~~############
	global temp_max, temp_min, length_max, length_min, stress_min, stress_max
	if temp > temp_max:
		temp_max = temp
	if temp < temp_min:
		temp_min = temp
	if length > length_max:
		length_max = length
	if length < length_min:
		length_min = length
	if stress < stress_min:
		stress_min = stress
	if stress > stress_max:
		stress_max = stress

def register_log(system_best, step_best, temp_best, length_best, T, step, stress_best):
	with open(system_best.path + 'log.txt', 'a+') as LOG:
		LOG.write('T = ' +str(T)+'\t step = '+str(step)+ '\n')
		LOG.write(str(step_best) + '\n' + str(temp_best) + '\n' + str(length_best) + '\n' + str(stress_best) + '\n')
		LOG.write(str(system_best.x)+'\n'+str(system_best.y) + '\n')

def register_step(system, step, temp, length, T, stress):
	with open(system.path + 'step.txt', 'a+') as LOG:
		LOG.write('T = ' +str(T)+'\t step = '+str(step)+ '\n')
		LOG.write(str(temp) + '\n' + str(length) + '\n' + str(stress) + '\n')
		LOG.write(str(system.x)+'\n'+str(system.y) + '\n')
		LOG.write(str(system.width)+'\n' + str(system.height)+'\n')

def anneal():
	# first step: read config and generate initial placement
	global temp_max, temp_min, length_max, length_min, stress_max, stress_min
	temp_max, temp_min, length_max, length_min, stress_max, stress_min = 0, 200, 0, 200, 0, 200
	system = config.read_config()
	system_new = deepcopy(system)
	system_best = deepcopy(system)
	step = 1
	step_best = 1
	system.gen_flp('step_'+str(step))
	system.combined_flp('step_'+str(step)) #Combine floorplan 
	
	#system.gen_ptrace('step_'+str(step))
	system.compute_power_density()
	#temp_current_prev = system.run_hotspot('step_'+str(step))
	#system.clean_hotspot('step_'+str(step))
	#print("160 Temp Current = ", temp_current_prev)
	layer_file = system.path +'step_'+str(step)+'combined_layers.txt'
	print(layer_file)
	temp_current,stress_current=thermal_mechanical_stress(layer_file,system.power_density)
	length_current = routing.solve_Cplex(system)
	temp_best, length_best, stress_best = temp_current, length_current, stress_current
	update_minmax(temp_current, length_current, stress_current)
	print ('step_'+str(step), 'temp =', temp_current, 'length =', length_current, 'stress =', stress_current)
	x_best, y_best = system.x[:], system.y[:]
	intp_size = system.intp_size
	granularity = system.granularity
	grid = block_occupation.initialize_grid(int(intp_size/granularity))
	for i in range(system.chiplet_count):
		grid = block_occupation.set_block_occupation(grid, granularity, system.x[i], system.y[i], system.width[i] + 2 * system.hubump[i], system.height[i] + 2 * system.hubump[i], i)
	# block_occupation.print_grid(grid)

	# set annealing parameters
	T = 1.0
	T_min = 0.01
	alpha = system.decay
	# jumping_ratio = T_min / alpha
	jumping_ratio = 0.9 # fixed to 10% chance to jump
	# start simulated annealing
	register_log(system_best, step_best, temp_best, length_best, T, step, stress_best)
	register_step(system, step, temp_current, length_current, T, stress_current)
	while T > T_min:
		i = 1
		while i <= intp_size:
			step += 1
			print ('step_'+str(step), ' T = ',T, ' i = ', i)
			jump_or_close = random.random()
			if 1 - jumping_ratio > jump_or_close:
				chiplet_moving, x_new, y_new, rotation = jumping_neighbor(system, grid)
			else:
				chiplet_moving, x_new, y_new = close_neighbor(system, grid)
				rotation = 0
			print ('moving chiplet', chiplet_moving + 2, 'from (', system.x[chiplet_moving], system.y[chiplet_moving], ') to (', x_new, y_new, '), rotation = ', rotation)
			system_new = deepcopy(system)
			system_new.x[chiplet_moving], system_new.y[chiplet_moving] = x_new, y_new
			if rotation == 1:
				system_new.rotate(chiplet_moving)
				# system_new.height[chiplet_moving], system_new.width[chiplet_moving] = system_new.width[chiplet_moving], system_new.height[chiplet_moving]
			system_new.gen_flp('step_' + str(step))
			system_new.gen_ptrace('step_'+str(step))
			system_new.combined_flp('step_'+str(step))#Combine floorplan 
			#temp_new_prev = system_new.run_hotspot('step_'+str(step))
			#system_new.clean_hotspot('step_'+str(step))
			layer_file=system_new.path + 'step_'+str(step)+'combined_layers.txt'
			print(layer_file)
			system_new.compute_power_density()
			temp_new, stress_new = thermal_mechanical_stress(layer_file,system_new.power_density)
			length_new = routing.solve_Cplex(system_new)
			print ('Temp =', temp_new, 'Length =', length_new, 'stress =', stress_new)
			update_minmax(temp_new, length_new, stress_new)
			register_step(system_new, step, temp_new, length_new, T, stress_new)
			# ap = accept_probability(temp_current, temp_new, T)
			ap, b, c = accept_probability(temp_current, temp_new, length_current, length_new, T, system.weight, stress_current, stress_new)
			r = random.random()
			if ap > r:
				# clear last step's occupation of chiplet_moving (system)
				grid = block_occupation.clear_block_occupation(grid, granularity, system.x[chiplet_moving], system.y[chiplet_moving], system.width[chiplet_moving] + 2 * system.hubump[chiplet_moving], system.height[chiplet_moving] + 2 * system.hubump[chiplet_moving], chiplet_moving)
				# set new occupation with rotation (system_new)
				grid = block_occupation.set_block_occupation(grid, granularity, x_new, y_new, system_new.width[chiplet_moving] + 2 * system.hubump[chiplet_moving], system_new.height[chiplet_moving] + 2 * system.hubump[chiplet_moving], chiplet_moving)
				# update system
				system = deepcopy(system_new)
				temp_current = temp_new
				length_current = length_new
				stress_current = stress_new
				bap, b, c = accept_probability(temp_best, temp_current, length_best, length_current, T, system.weight, stress_best, stress_current)
				if bap >=1:
				# if temp_new < temp_best:
					temp_best = temp_new
					length_best = length_new
					stress_best = stress_new
					system_best = deepcopy(system_new)
					step_best = step
				print ('AP = ', ap, ' > ', r, ' Accept!')
				# block_occupation.print_grid(grid)
			else:
				print ('AP = ', ap, ' < ', r, ' Reject!')
			i += 1
			with open(system_best.path + 'variables.txt', 'a+') as LOG:
						LOG.write('iteration = ' +str(i)+'\t b = '+str(b)+ '\t c = '+str(c)+ '\t stress_current = '+str(stress_current)+ '\t temp_current = '+str(temp_current)+  '\t length_current = '+str(length_current)+'\n')
       
		register_log(system_best, step_best, temp_best, length_best, T, step, stress_best)
		T *= alpha
		# jumping_ratio /= alpha
	os.system('rm ' + system.path + '{*.flp,*.lcf,*.ptrace,*.steady}')
	# os.system('gs -dBATCH -dNOPAUSE -q -sDEVICE=pdfwrite -sOutputFile='+system.path+'combine.pdf '+system.path + 'step_{1..'+str(step_best)+'}L4.pdf')
	os.system('rm ' + system.path + 'step_*.pdf')
	return system_best, step_best, temp_best, length_best, stress_best

if __name__ == "__main__":
	solution, step_best, temp_best, length_best, stress_best = anneal()
	print ('final solution: step, temp')
	print (step_best)
	print (temp_best)
	print (length_best)
	print (stress_best)
	print (solution.x)
	print (solution.y)
	with open(solution.path+'output.txt','w') as OUTPUT:
		OUTPUT.write(str(step_best) + '\n' + str(temp_best) + '\n' + str(length_best) + '\n' + str(stress_best) + '\n')
		OUTPUT.write(str(solution.x)+ '\n' + str(solution.y) + '\n')


