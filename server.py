import platform
import socket
import time
from subprocess import Popen, PIPE

import psutil


class Server:

    def get_dmi(self):
        p = Popen('dmidecode', stdout=PIPE, shell=True)
        stdout, stderr = p.communicate()
        return stdout.decode()

    def get_mem_total(self):
        memtotal=  round( psutil.virtual_memory().total / 2**30,1)
        return str(memtotal) + 'GB'


    def get_cpu_model(self):
        cmd = "cat /proc/cpuinfo"
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
        stdout, stderr = p.communicate()
        return stdout.decode()

    def get_cpu_cores(self):
        cpu_cores = {"physical": psutil.cpu_count(logical=False) or 0,
                     "logical": psutil.cpu_count()}
        return cpu_cores

    def get_disk_info(self):
        ret = []
        cmd = "fdisk -l|egrep '^Disk\s/dev/[a-z]+:\s\w*'"
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
        stdout, stderr = p.communicate()
        for i in stdout.decode().split('\n'):
            disk_info = i.split(",")
            if disk_info[0]:
                ret.append(disk_info[0])
        return ret

    def parser_cpu(self, stdout):
        groups = [i for i in stdout.split('\n\n')]
        group = groups[-2]
        cpu_list = [i for i in group.split('\n')]
        cpu_info = {}
        for x in cpu_list:
            k, v = [i.strip() for i in x.split(':')]
            cpu_info[k] = v
        return cpu_info

    def parser_dmi(self, dmidata):
        pd = {}
        line_in = False
        for line in dmidata.split('\n'):
            if line.startswith('System Information'):
                line_in = True
                continue
            if line.startswith('\t') and line_in:
                k, v = [i.strip() for i in line.split(':')]
                pd[k] = v
            else:
                line_in = False
        return pd

    @property
    def ip(self):
        try:
            hostname = socket.getfqdn(socket.gethostname())
            ipaddr = socket.gethostbyname(hostname)
        except Exception as msg:
            print(msg)
            ipaddr = ''
        return ipaddr

    @property
    def cpu(self):
        sys_cpu = {}
        cpu_time = psutil.cpu_times_percent(interval=1)
        sys_cpu['percent'] = psutil.cpu_percent(interval=1)
        sys_cpu['lcpu_percent'] = psutil.cpu_percent(interval=1, percpu=True)
        sys_cpu['user'] = cpu_time.user
        sys_cpu['nice'] = cpu_time.nice
        sys_cpu['system'] = cpu_time.system
        sys_cpu['idle'] = cpu_time.idle
        sys_cpu['iowait'] = cpu_time.iowait
        sys_cpu['irq'] = cpu_time.irq
        sys_cpu['softirq'] = cpu_time.softirq
        sys_cpu['guest'] = cpu_time.guest
        return sys_cpu

    @property
    def memory(self):
        sys_mem = {}
        mem = psutil.virtual_memory()
        sys_mem["total"] = mem.total / 1024 / 1024
        sys_mem["percent"] = mem.percent
        sys_mem["available"] = mem.available / 1024 / 1024
        sys_mem["used"] = mem.used / 1024 / 1024
        sys_mem["free"] = mem.free / 1024 / 1024
        sys_mem["buffers"] = mem.buffers / 1024 / 1024
        sys_mem["cached"] = mem.cached / 1024 / 1024
        return sys_mem

    def _parser_sys_disk(self, mountpoint):
        partitions_list = {}
        d = psutil.disk_usage(mountpoint)
        partitions_list['mountpoint'] = mountpoint
        partitions_list['total'] = round(d.total / 1024 / 1024 / 1024.0, 2)
        partitions_list['free'] = round(d.free / 1024 / 1024 / 1024.0, 2)
        partitions_list['used'] = round(d.used / 1024 / 1024 / 1024.0, 2)
        partitions_list['percent'] = d.percent
        return partitions_list

    @property
    def disk(self):
        sys_disk = {}
        partition_info = []
        partitions = psutil.disk_partitions()
        for p in partitions:
            partition_info.append(self._parser_sys_disk(p.mountpoint))
        sys_disk = partition_info
        return sys_disk

    def _get_nic(self):
        key_info = psutil.net_io_counters(pernic=True).keys()  # 获取网卡名称
        recv = {}
        sent = {}
        for key in key_info:
            recv.setdefault(key, psutil.net_io_counters(pernic=True).get(key).bytes_recv)
            sent.setdefault(key, psutil.net_io_counters(pernic=True).get(key).bytes_sent)

        return key_info, recv, sent

    def _get_nic_rate(self, func):
        key_info, old_recv, old_sent = func()  # 上一秒收集的数据
        time.sleep(1)
        key_info, now_recv, now_sent = func()  # 当前所收集的数据

        net_in = {}
        net_out = {}

        for key in key_info:
            net_in.setdefault(key, (now_recv.get(key) - old_recv.get(key)) / 1024)  # 每秒接收速率
            net_out.setdefault(key, (now_sent.get(key) - old_sent.get(key)) / 1024)  # 每秒发送速率

        return key_info, net_in, net_out

    @property
    def net(self):
        net_info = []
        key_info, net_in, net_out = self._get_nic_rate(self._get_nic)
        for key in key_info:
            in_data = net_in.get(key)
            out_data = net_out.get(key)
            net_info.append({"nic_name": key, "traffic_in": in_data, "traffic_out": out_data})
        return net_info

    def status(self):
        status = {'hostname': platform.node(),
                  'cpu': self.cpu,
                  'mem': self.memory,
                  'disk': self.disk,
                  'net': self.net}

        return status

    def configuration(self):
        hardware = {}
        hardware['memory'] = self.get_mem_total()
        hardware['disk'] = str(self.get_disk_info())
        cpuinfo = self.parser_cpu(self.get_cpu_model())
        cpucore = self.get_cpu_cores()

        hardware['cpu_num'] = cpucore.get('logical', None)
        hardware['cpu_physical'] = cpucore.get('physical')
        hardware['cpu_model'] = cpuinfo.get('model name')
        hardware['ip'] = self.ip
        hardware['osver'] =  platform.platform()
        hardware['hostname'] = platform.node()

        hardware['sn'] = self.parser_dmi(self.get_dmi()).get('Serial Number')
        hardware['vendor'] = self.parser_dmi(self.get_dmi()).get('Manufacturer')
        hardware['product'] = self.parser_dmi(self.get_dmi()).get('Version')

        return hardware
