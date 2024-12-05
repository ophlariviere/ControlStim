import sys
from PyQt5.QtWidgets import (
    QApplication,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QPushButton,
    QWidget,
    QGroupBox,
    QSpinBox,
)

from pyScienceMode import Channel, Device, Modes
from pyScienceMode import RehastimP24 as St
import logging

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)
if not logging.getLogger().hasHandlers():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )


# Interface utilisateur
class VisualizationWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stimulateur Configurator")
        self.layout = QVBoxLayout(self)

        # Liste des canaux configurés
        self.channels = []
        self.stimulator = None

        # Sélection des canaux
        self.channel_selection_group = QGroupBox("Sélectionnez les canaux")
        self.channel_selection_layout = QHBoxLayout()
        self.channel_selection_group.setLayout(self.channel_selection_layout)

        self.checkboxes = []
        self.channel_inputs = {}  # Stockage des inputs pour chaque canal

        for i in range(1, 9):  # Channels 1 à 8
            checkbox = QCheckBox(f"Channel {i}")
            checkbox.stateChanged.connect(self.update_channel_inputs)
            self.checkboxes.append(checkbox)
            self.channel_selection_layout.addWidget(checkbox)

        self.layout.addWidget(self.channel_selection_group)

        # Section paramètres des canaux
        self.channel_config_group = QGroupBox("Configurer les paramètres des canaux")
        self.channel_config_layout = QVBoxLayout()
        self.channel_config_group.setLayout(self.channel_config_layout)
        self.layout.addWidget(self.channel_config_group)

        # Boutons pour contrôler la stimulation
        self.control_layout = QHBoxLayout()
        self.start_button = QPushButton("Démarrer Stimulation")
        self.start_button.clicked.connect(self.start_stimulation)
        self.update_button = QPushButton("Mettre à Jour Stimulation")
        self.update_button.clicked.connect(self.update_stimulation)
        self.stop_button = QPushButton("Arrêter Stimulation")
        self.stop_button.clicked.connect(self.stop_stimulation)

        self.control_layout.addWidget(self.start_button)
        self.control_layout.addWidget(self.update_button)
        self.control_layout.addWidget(self.stop_button)
        self.layout.addLayout(self.control_layout)
        self.stimulator_is_active = False

    def update_channel_inputs(self):
        selected_channels = [
            i + 1 for i, checkbox in enumerate(self.checkboxes) if checkbox.isChecked()
        ]

        # Ajouter les nouveaux canaux sélectionnés
        for channel in selected_channels:
            if channel not in self.channel_inputs:
                channel_layout = QHBoxLayout()

                name_input = QLineEdit()
                name_input.setPlaceholderText(f"Canal {channel} - Nom")
                amplitude_input = QSpinBox()
                amplitude_input.setRange(0, 100)
                amplitude_input.setPrefix("Amp ")
                pulse_width_input = QSpinBox()
                pulse_width_input.setRange(0, 1000)
                pulse_width_input.setPrefix("µs ")
                frequency_input = QSpinBox()
                frequency_input.setRange(0, 200)
                frequency_input.setPrefix("Hz ")
                mode_input = QComboBox()
                mode_input.addItems([mode.name for mode in Modes])

                channel_layout.addWidget(name_input)
                channel_layout.addWidget(amplitude_input)
                channel_layout.addWidget(pulse_width_input)
                channel_layout.addWidget(frequency_input)
                channel_layout.addWidget(mode_input)

                self.channel_config_layout.addLayout(channel_layout)
                self.channel_inputs[channel] = {
                    "layout": channel_layout,
                    "name_input": name_input,
                    "amplitude_input": amplitude_input,
                    "pulse_width_input": pulse_width_input,
                    "frequency_input": frequency_input,
                    "mode_input": mode_input,
                }

        # Supprimer les canaux désélectionnés
        for channel in list(self.channel_inputs.keys()):
            if channel not in selected_channels:
                inputs = self.channel_inputs.pop(channel)
                for i in reversed(range(inputs["layout"].count())):
                    widget = inputs["layout"].itemAt(i).widget()
                    if widget:
                        widget.setParent(None)

    def start_stimulation(self, channel_to_send):
        try:
            if self.stimulator is None:
                logging.warning(
                    "Stimulateur non initialisé. Veuillez le configurer avant de démarrer."
                )
                return

            self.channels = []
            for channel, inputs in self.channel_inputs.items():
                if channel in channel_to_send:
                    channel_obj = Channel(
                        no_channel=channel,
                        name=inputs["name_input"].text(),
                        amplitude=inputs["amplitude_input"].value(),
                        pulse_width=inputs["pulse_width_input"].value(),
                        frequency=inputs["frequency_input"].value(),
                        mode=inputs["mode_input"].currentText(),
                        device_type=Device.Rehastimp24,
                    )
                else:
                    channel_obj = Channel(
                        no_channel=channel,
                        name=inputs["name_input"].text(),
                        amplitude=0,
                        pulse_width=inputs["pulse_width_input"].value(),
                        frequency=inputs["frequency_input"].value(),
                        mode=inputs["mode_input"].currentText(),
                        device_type=Device.Rehastimp24,
                    )
                self.channels.append(channel_obj)

            self.stimulator.init_stimulation(list_channels=self.channels)
            self.stimulator.start_stimulation(
                upd_list_channels=self.channels, safety=True
            )
            logging.info(f"Stimulation démarrée sur les canaux {channel_to_send}")
        except Exception as e:
            logging.error(f"Erreur lors du démarrage de la stimulation : {e}")

    def stop_stimulation(self):
        try:
            if self.stimulator:
                # self.pause_stimulation()
                self.stimulator.end_stimulation()
                self.stimulator.close_port()
                self.stimulator_is_active = False
                self.stimulator = None
                logging.info("Stimulateur arrêtée.")
            else:
                logging.warning("Aucun stimulateur actif à arrêter.")
        except Exception as e:
            logging.error(f"Erreur lors de l'arrêt de la stimulation : {e}")

    def pause_stimulation(self):
        try:
            if self.stimulator:
                self.stimulator.end_stimulation()
                logging.info("Stimulation arrêtée.")
            else:
                logging.warning("Aucun stimulateur actif à arrêter.")
        except Exception as e:
            logging.error(f"Erreur lors de l'arrêt de la stimulation : {e}")

    def update_stimulation(self):
        if self.stimulator is None:
            self.stimulator = St(port="COM3", show_log="Status")
            self.stimulator_is_active = True


if __name__ == "__main__":
    app = QApplication(sys.argv)
    sys.exit(app.exec_())
