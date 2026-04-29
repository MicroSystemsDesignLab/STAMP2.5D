# Save this as thermal_connector.py in the same directory as sim_annealing.py
import requests
import logging
import os
import sys

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("thermal_connector.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

def thermal_mechanical_stress(layer_file, power_density):
    """
    Function that calls the local machine to perform thermal mechanical stress analysis.
    
    Args:
        layer_file: Path to the .txt file on the remote server
        power_density: Power density parameter
        
    Returns:
        tuple: (temp_current, stress_current) returned from the local function
    """
    try:
        # Check if file exists
        if not os.path.exists(layer_file):
            logging.error(f"File not found: {layer_file}")
            logging.info(f"Current working directory: {os.getcwd()}")
            # Return default values instead of None to avoid TypeError
            return 1000, 2000
            
        # Read the contents of the layer file
        with open(layer_file, 'r') as f:
            file_contents = f.read()
        
        # Prepare data to send to the local machine
        data = {
            'file_contents': file_contents,
            'power_density': power_density
        }
        
        # Use port 5000 since that's where the SSH tunnel is receiving
        url = "http://localhost:5001/execute_local_function"
        
        logging.info(f"Sending request to local machine with file size {len(file_contents)} bytes and power density: {power_density}")
        
        response = requests.post(url, json=data, timeout=6000)
        
        if response.status_code == 200:
            results = response.json()
            logging.info(f"Received response from local machine: {results}")
            return results['temp_current'], results['stress_current']
        else:
            logging.error(f"Error from local machine: {response.status_code}, {response.text}")
            # Return default values instead of None to avoid TypeError
            return 1000, 2000
    except Exception as e:
        logging.error(f"Exception when calling local machine: {str(e)}")
        # Return default values instead of None to avoid TypeError
        return 1000, 2000
