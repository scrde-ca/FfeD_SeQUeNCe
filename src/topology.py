import math
import numpy
import json5
import pandas as pd

from process import Process
from entity import Entity
from event import Event


class TemperatureModel():
    df = pd.DataFrame()

    def read_temperature_file(self,filename):
        self.df = pd.read_csv(filename)
        print (filename,self.df)
        return self.df

    def temperature_from_time(self,time):
        ## TODO
        ## interpolation of time
        temperature = 60
        return temperature


class Photon(Entity):
    def __init__(self, name, timeline, **kwargs):
        Entity.__init__(self, name, timeline)
        self.wavelength = kwargs.get("wavelength", 0)
        self.location = kwargs.get("location", None)
        self.encoding_type = kwargs.get("encoding_type")
        self.quantum_state = kwargs.get("quantum_state", 45) ## 45 degrees instead of pi/4

    def init(self):
        pass

    def random_noise(self):
        self.quantum_state += numpy.random.random() * 360  # add random angle, use 360 instead of 2*pi

    def measure(self, basis):
        # alpha = numpy.dot(self.quantum_state, basis[0])  # projection onto basis vector
        alpha = numpy.cos((self.quantum_state - basis[0])/180.0 * numpy.pi)
        if numpy.random.random_sample() < alpha ** 2:
            self.quantum_state = basis[0]
            return 0
        self.quantum_state = basis[1]
        return 1


class OpticalChannel(Entity):
    def __init__(self, name, timeline, **kwargs):
        Entity.__init__(self, name, timeline)
        self.attenuation = kwargs.get("attenuation", 0)
        self.distance = kwargs.get("distance", 0)
        self.temperature = kwargs.get("temperature", 0)
        self.polarization_fidelity = kwargs.get("polarization_fidelity", 1)
        self.sender = None
        self.receiver = None
        self.light_speed = kwargs.get("light_speed",
                                      3 * 10 ** -4)  # used for photon timing calculations (measured in m/ps)

    def init(self):
        pass

    def transmit(self, photon):
        pass

    def set_sender(self, sender):
        self.sender = sender

    def set_receiver(self, receiver):
        self.receiver = receiver

    def set_distance(self, distance):
        self.distance = distance

    def distance_from_time(self, time):
        distance = self.distance
        ## TODO: distance as a function of temperature
        temperature = self.tModel.temperature_from_time(time)

        return distance

    def set_temerature_model(self, filename):
        self.tModel = TemperatureModel()
        self.tModel.read_temperature_file(filename)


class QuantumChannel(OpticalChannel, Entity):
    def transmit(self, photon):
        # generate chance to lose photon
        loss = self.distance * self.attenuation
        chance_photon_kept = 10 ** (loss / -10)

        # check if photon kept
        if numpy.random.random_sample() < chance_photon_kept:
            # check if random polarization noise applied
            if numpy.random.random_sample() > self.polarization_fidelity:
                photon.random_noise()
            # schedule receiving node to receive photon at future time determined by light speed
            future_time = self.timeline.now() + int(self.distance / self.light_speed)
            process = Process(self.receiver, "detect", [photon])

            event = Event(future_time, process)
            self.timeline.schedule(event)


class ClassicalChannel(OpticalChannel, Entity):
    def transmit(self, message):
        future_time = self.timeline.now() + int(self.distance / self.light_speed)
        process = Process(self.receiver, "receive_message", [message])
        event = Event(future_time, process)
        self.timeline.schedule(event)


class LightSource(Entity):
    def __init__(self, name, timeline, **kwargs):
        Entity.__init__(self, name, timeline)
        self.frequency = kwargs.get("frequency", 0)  # measured in Hz
        self.wavelength = kwargs.get("wavelength", 0)  # measured in nm
        self.mean_photon_num = kwargs.get("mean_photon_num", 0)
        self.encoding_type = kwargs.get("encoding_type")
        self.direct_receiver = kwargs.get("direct_receiver", None)
        # qs_array = kwargs.get("quantum_state", [[math.sqrt(1 / 2), 0], [math.sqrt(1 / 2), 0]])
        self.quantum_state = kwargs.get("quantum_state", 45)  # polarization angle 45 degrees instead of pi/4
        self.photon_counter = 0

    def init(self):
        pass

    def emit(self, state_list):
        time = self.timeline.now()

        for state in state_list:
            num_photons = numpy.random.poisson(self.mean_photon_num)

            for _ in range(num_photons):
                new_photon = Photon(None, self.timeline,
                                    wavelength=self.wavelength,
                                    location=self.direct_receiver,
                                    encoding_type=self.encoding_type,
                                    quantum_state=state)
                process = Process(self.direct_receiver, "transmit", [new_photon])
                event = Event(time, process)
                self.timeline.schedule(event)

                self.photon_counter += 1

            time += (10 ** 12) / self.frequency

    def assign_receiver(self, receiver):
        self.direct_receiver = receiver


class QSDetector(Entity):
    def __init__(self, name, timeline, **kwargs):
        Entity.__init__(self, name, timeline)
        detector_0 = kwargs.get("detector_0", None)
        detector_1 = kwargs.get("detector_1", None)
        self.detectors = [detector_0, detector_1]
        self.splitter = kwargs.get("splitter")

    def init(self):
        pass

    def detect(self, photon):
        self.detectors[self.splitter.transmit(photon)].detect()


class Detector(Entity):
    def __init__(self, name, timeline, **kwargs):
        Entity.__init__(self, name, timeline)
        self.efficiency = kwargs.get("efficiency", 1)
        self.dark_count = kwargs.get("dark_count", 0)  # measured in Hz
        self.count_rate = kwargs.get("count_rate", math.inf)  # measured in Hz
        self.time_resolution = kwargs.get("time_resolution", 0)  # measured in ps
        self.photon_times = []
        self.next_detection_time = 0

    def init(self):
        self.add_dark_count()

    def detect(self):
        if numpy.random.random_sample() < self.efficiency and self.timeline.now() > self.next_detection_time:
            time = int(self.timeline.now() / self.time_resolution) * self.time_resolution
            self.photon_times.append(time)
            self.next_detection_time = self.timeline.now() + (10 ** 12 / self.count_rate)  # period in ps

    def add_dark_count(self):
        time_to_next = int(numpy.random.exponential(self.dark_count) * (10 ** 12))  # time interval to next dark count
        time = time_to_next + self.timeline.now()  # time of next dark count

        process1 = Process(self, "add_dark_count", [])  # schedule photon detection and dark count add in future
        process2 = Process(self, "detect", [])
        event1 = Event(time, process1)
        event2 = Event(time, process2)
        self.timeline.schedule(event1)
        self.timeline.schedule(event2)


class BeamSplitter(Entity):
    def __init__(self, name, timeline, **kwargs):
        Entity.__init__(self, name, timeline)
        self.basis = kwargs.get("basis", [0, 90])
        self.fidelity = kwargs.get("fidelity", 1)

    def init(self):
        pass

    def transmit(self, photon):
        if numpy.random.random_sample() < self.fidelity:
            return photon.measure(self.basis)

    def set_basis(self, basis):
        self.basis = basis


class Node(Entity):
    def __init__(self, name, timeline, **kwargs):
        Entity.__init__(self, name, timeline)
        self.components = kwargs.get("components", {})
        self.message = None
        self.protocol = None

    def init(self):
        pass

    def send_photons(self, basis_list, bit_list, source_name):
        # message that photon pulse is beginning
        self.send_message("begin_photon_pulse")

        # use emitter to send photon over connected channel to node
        state_list = []
        for i in bit_list:
            state_list.append(basis_list[i][bit_list[i]])

        self.components[source_name].emit(state_list)

        # schedule event to message that photon pulse is finished
        future_time = self.timeline.now() + len(state_list) * (10 ** 12 / self.components[source_name].frequency)
        process = Process(self, "send_message", ["end_photon_pulse"])
        event = Event(future_time, process)
        self.timeline.schedule(event)

    def receive_photon(self, photon, detector_name):
        self.components[detector_name].detect(photon)

    def get_detector_count(self):
        detector = self.components['detector']  # QSDetector class

        # return length of photon time lists from two Detectors within QSDetector
        return [len(detector.detectors[0].photon_times), len(detector.detectors[1].photon_times)]

    def get_source_count(self):
        source = self.components['lightsource']
        return source.photon_counter

    def send_message(self, msg):
        self.components['cchannel'].transmit(msg, self)

    def receive_message(self, msg):
        self.message = msg
        self.protocol.received_message()


class Topology:
    def __init__(self, config_file, timelines):
        self.nodes = {}
        self.quantum_channel = {}
        self.entities = []

        topo_config = json5.load(open(config_file))
        nodes_config = topo_config['nodes']
        self.create_nodes(nodes_config, timelines)
        qchannel_config = topo_config['QChannel']
        self.create_qchannel(qchannel_config, timelines)

    def create_nodes(self, nodes_config, timelines):
        for node_config in nodes_config:
            components = {}

            for component_config in node_config['components']:
                if component_config['name'] in components:
                    raise Exception('two components have same name')

                # get component_name, timeline, and name
                # then delete entries in component_config dictionary to prevent conflicting values
                component_name = component_config['name']
                name = node_config['name'] + '.' + component_name
                tl = timelines[component_config['timeline']]
                del component_config['name']
                del component_config['timeline']

                # light source instantiation
                if component_config["type"] == 'LightSource':
                    ls = LightSource(name, tl, **component_config)
                    components[component_name] = ls
                    self.entities.append(ls)

                # detector instantiation
                elif component_config["type"] == 'QSDetector':
                    detector = Detector(name, tl, **component_config)
                    components[component_name] = detector
                    self.entities.append(detector)

                else:
                    raise Exception('unknown device type')

            node = Node(node_config['name'], timelines[node_config['timeline']], components=components)
            self.entities.append(node)

            if node.name in self.nodes:
                raise Exception('two nodes have same name')

            self.nodes[node.name] = node

    def create_qchannel(self, qchannel_config, timelines):
        for qc_config in qchannel_config:
            name = qc_config['name']
            tl = timelines[qc_config['timeline']]
            del qc_config['name']
            del qc_config['timeline']

            qc = OpticalChannel(name, tl, **qc_config)

            sender = self.find_entity_by_name(qc_config['sender'])
            receiver = self.find_entity_by_name(qc_config['receiver'])

            qc.set_sender(sender)
            sender.direct_receiver = qc
            qc.set_receiver(receiver)
            self.entities.append(qc)

    def print_topology(self):
        pass

    def to_json5_file(self):
        pass

    def find_entity_by_name(self, name):
        for e in self.entities:
            if e.name == name:
                return e
        raise Exception('unknown entity name')

    def find_node_by_name(self, name):
        pass

    def find_qchannel_by_name(self, name):
        pass
