from abc import ABC, abstractmethod
import paramiko
import time
from system_config import IMAGE_NAME, LOCAL_SSH_PUBLIC_KEY_PATH, SSH_KEY_USERNAME, SSH_USER

class Node(ABC):
    def __init__(self, driver, location, name, machine_type, master=False, masterNode=None):
        self.driver = driver
        self.location = location
        self.name = name
        self.machine_type = machine_type
        if not master and masterNode == None:
            raise ValueError("Slave nodes need a master")
        self.master = masterNode
        self.disk = self.driver.create_volume(40, f"boot-{self.name}", image=IMAGE_NAME, location=self.location)
        self.node = self.driver.create_node(
            name, self.machine_type, None, location=self.location, ex_boot_disk=self.disk)
        self.driver.wait_until_running([self.node])
        self.pubip = self.node.public_ips[0]
        self.privip = self.node.private_ips[0]
        self.connected = False

        for i in range(5):  # Try 5 times
            try:
                self.open_ssh()
                break
            except Exception as e:
                print(e)
                time.sleep(5)
        if not self.connected:
            raise RuntimeError(f"Can't connect to node {self.name}")
        self.start_type()

    def __del__(self):
        self.close_ssh()

    def open_ssh(self):
        pkey = paramiko.RSAKey(filename=LOCAL_SSH_PUBLIC_KEY_PATH)
        self.ssh = paramiko.SSHClient()
        self.ssh.load_system_host_keys()
        self.ssh.set_missing_host_key_policy(paramiko.WarningPolicy())
        self.ssh.connect(self.pubip, port=22, username=SSH_KEY_USERNAME, pkey=pkey)
        self.connected = True

    def close_ssh(self):
        self.connected = False
        if self.ssh:
            self.ssh.close()

    @abstractmethod
    def start_type(self):
        pass


class MasterNode(Node):
    def start_type(self):
        print(f'Master {self.privip} succesfully started')
        stdin, stdout, stderr = self.ssh.exec_command(f'echo "SPARK_MASTER_HOST=\'{self.privip}\'" >> /home/{SSH_USER}/bd/spark/conf/spark-env.sh')
        if (len(stderr.read()) > 0):
            print(stdout.read())
            print(stderr.read())

        stdin, stdout, stderr = self.ssh.exec_command(
            f'sudo /home/{SSH_USER}/bd/spark/sbin/start-master.sh')
        if (len(stderr.read()) > 0):
            print(stdout.read())
            print(stderr.read())


class SlaveNode(Node):
    def start_type(self):
        print('Slave succesfully started')
        stdin, stdout, stderr = self.ssh.exec_command(f'sudo /home/{SSH_USER}/bd/spark/sbin/start-slave.sh spark://{self.master.privip}:7077')
        if (len(stderr.read()) > 0):
            print(stdout.read())
            print(stderr.read())