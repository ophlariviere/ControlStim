import threading
import time
import numpy as np
from biosiglive import TcpClient
from PyQt5.QtCore import QObject
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')



class DataReceiver(QObject):
    def __init__(self, server_ip, server_port, visualization_widget, read_frequency=100, threshold=30):
        super().__init__()
        self.visualization_widget = visualization_widget
        self.server_ip = server_ip
        self.server_port = server_port
        self.tcp_client = TcpClient(self.server_ip, self.server_port, read_frequency=read_frequency)
        self.threshold = threshold
        self.stimulator = []
        self.datacycle = {}
        self.sendStim = False
        self.timeStim = 0
        self.visualization_widget = visualization_widget
        self.read_frequency = read_frequency

    def start_receiving(self):
        logging.info("Début de la réception des données...")
        while True:
            tic = time.time()
            try:
                received_data = self.tcp_client.get_data_from_server(command=['Force'])
                if 'Force' not in received_data or not received_data['Force']:
                    logging.warning("Aucune donnée reçue depuis le serveur.")
                    continue

                # Organisation des données reçues pour PF1 et PF2
                frc_data = {}
                for pfnum in [1, 2]:
                    start_idx = (pfnum - 1) * 9  # PF1: 0-8, PF2: 9-17
                    for i, comp in enumerate(['Force', 'Moment', 'CoP']):
                        key = f"{comp}_{pfnum}"
                        frc_data[key] = np.array([
                            received_data['Force'][start_idx + 3 * i][:],
                            received_data['Force'][start_idx + 3 * i + 1][:],
                            received_data['Force'][start_idx + 3 * i + 2][:]
                        ])

                received_data = {"Force": frc_data}

                self.check_stimulation(received_data)
                self.process_data(received_data)

                loop_time = time.time() - tic
                real_time_to_sleep = max(0, 1 / self.read_frequency - loop_time)
                time.sleep(real_time_to_sleep)

            except Exception as e:
                logging.error(f"Erreur lors de la réception des données : {e}")

    def check_stimulation(self, received_data):
        try:
            for PFnum in range(1, 3):
                ap_force_mean = np.mean(received_data['Force']['Force_' + str(PFnum)][0, :])
                long = len(received_data['Force']['Force_' + str(PFnum)][0, :])
                if 'Force' in self.datacycle and len(self.datacycle['Force']['Force_' + str(PFnum)][0, :]) > 0:
                    last_ap_force_mean = np.mean(self.datacycle['Force']['Force_' + str(PFnum)][0, -long:])
                else:
                    last_ap_force_mean = 0
                """
                if PFnum == 1:
                    print(last_ap_force_mean, ap_force_mean)
                """

                # Accédez à stimulator_is_active via self.visualization_widget
                if ((ap_force_mean - last_ap_force_mean) > 0) and (self.sendStim is False) and (ap_force_mean < -20):
                    if self.visualization_widget.stimulator_is_active:  # Vérifiez si le stimulateur est actif
                        channel_to_stim = [1, 2, 3, 4] if PFnum == 1 else [5, 6, 7, 8]
                        self.visualization_widget.start_stimulation(channel_to_stim)

                        self.sendStim = True
                        self.timeStim = time.time()

                elif ((((ap_force_mean-last_ap_force_mean) < 0) and (self.sendStim is True) and (ap_force_mean > 10) and ((time.time() - self.timeStim) > 0.2))
                      or ((time.time() - self.timeStim) > 0.5) and (self.sendStim is True)):
                    if self.visualization_widget.stimulator_is_active == True:  # Vérifiez si le stimulateur est actif
                        self.visualization_widget.pause_stimulation()
                        self.sendStim = False
        except Exception as e:
            logging.error(f"Erreur lors de la stimulation : {e}")

    def process_data(self, received_data):
        self.check_cycle(received_data)
        self.recursive_concat(self.datacycle, received_data)

    def check_cycle(self, received_data):
        try:
            vertical_force_mean = np.mean(received_data['Force']['Force_1'][2, :])
            long = len(received_data['Force']['Force_1'][2, :])
            if 'Force' in self.datacycle and len(self.datacycle['Force']['Force_1'][2, :]) > 0:
                last_vertical_force_mean = np.mean(self.datacycle['Force']['Force_1'][2, -long:])
            else:
                last_vertical_force_mean = 0

            if vertical_force_mean > self.threshold > last_vertical_force_mean != 0:
                cycle_to_process = self.datacycle
                self.datacycle = {}
                self.current_frame = 0
                logging.info("Les données ont été réinitialisées pour un nouveau cycle.")
                #self.processor.start_new_cycle(cycle_to_process)

        except Exception as e:
            logging.error(f"Erreur lors de la vérification du cycle : {e}")


    def process_data(self, received_data):
        self.check_cycle(received_data)
        self.recursive_concat(self.datacycle, received_data)


    def recursive_concat(self, datacycle, received_data):
        for key, value in received_data.items():
            if isinstance(value, dict):
                if key not in datacycle:
                    datacycle[key] = {}
                self.recursive_concat(datacycle[key], value)
            else:
                try:
                    datacycle[key] = np.hstack((datacycle[key], value)) if key in datacycle else value
                except Exception as e:
                    logging.error(f"Erreur lors de la concaténation des données pour la clé '{key}': {e}")
