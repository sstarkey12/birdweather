import csv

def write_csv(file_path, data):
    """Write single row to csv file 

    Args:
        file_path (str): filename
        data (list): ['data1', 'datat2', 'data3']
    """
    with open(file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(data)

if __name__ == '__main__':
    pass