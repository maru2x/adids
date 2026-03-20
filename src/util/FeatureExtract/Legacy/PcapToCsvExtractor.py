import time
import warnings
from concurrent.futures import ProcessPoolExecutor

import pandas as pd
import pytz
from scapy.layers.inet import IP, UDP, TCP
from scapy.sendrecv import sniff

warnings.simplefilter('ignore')

from datetime import datetime, timezone, timedelta
import os
import ipaddress
import json


def extract_features_from_packet(pkt, malicious_addresses, benign_addresses):
    # 有効なパケットであればそのFieldを、そうでなければNoneを返す
    timestamp = pkt.time
    src = pkt[IP].src
    dst = pkt[IP].dst
    length = pkt[IP].len
    if pkt[IP].proto == 6:
        protocol = "tcp"
    elif pkt[IP].proto == 17:
        protocol = "udp"
    else:
        protocol = None
    port = -1
    tcp_flag = None

    # src : malicious address
    # パケットの送信元IPアドレスが、指定された悪意のあるIPアドレスのリストに含まれている時
    if src in malicious_addresses:
        direction = "snd"
        external_network_address = dst
        internal_network_address = src
        label = 1
        if protocol == "tcp":
            port = pkt[TCP].sport
            tcp_flag = str(pkt[TCP].flags)
        elif protocol == "udp":
            port = pkt[UDP].sport
            tcp_flag = -1

    # dst : malicious address
    # パケットの宛先IPアドレスが、指定された悪意のあるIPアドレスのリストに含まれている時
    elif dst in malicious_addresses:
        direction = "rcv"
        external_network_address = src
        internal_network_address = dst
        label = 1
        if protocol == "tcp":
            port = pkt[TCP].dport
            tcp_flag = str(pkt[TCP].flags)
        elif protocol == "udp":
            port = pkt[UDP].dport
            tcp_flag = -1

    # src : benign address
    # パケットの送信元IPアドレスが、指定された良性のあるIPアドレスのリストに含まれている時(内部間での通信はキャプチャしない)
    elif src in benign_addresses and dst not in benign_addresses:
        direction = "snd"
        external_network_address = dst
        internal_network_address = src
        label = 0
        if protocol == "tcp":
            port = pkt[TCP].sport
            tcp_flag = str(pkt[TCP].flags)
        elif protocol == "udp":
            port = pkt[UDP].sport
            tcp_flag = -1

    # dst : benign address
    #パケットの宛先IPアドレスが、指定された良性のあるIPアドレスのリストに含まれている時(内部間での通信はキャプチャしない)
    elif dst in benign_addresses and src not in benign_addresses:
        direction = "rcv"
        external_network_address = src
        internal_network_address = dst
        label = 0
        if protocol == "tcp":
            port = pkt[TCP].dport
            tcp_flag = str(pkt[TCP].flags)
        elif protocol == "udp":
            port = pkt[UDP].dport
            tcp_flag = -1

    # それ以外のパケットは関係のないものとして破棄
    else:
        return (None,None),None

    return (external_network_address,internal_network_address),[timestamp,direction,protocol,port,tcp_flag,length,label]


def extract_features_from_flow(packets_in_flow):
    # フロー単位にまとめられたパケット(packets_in_flow)から特徴量を抽出
    rcv_packet_count = 0
    snd_packet_count = 0
    tcp_count = 0
    udp_count = 0
    most_port = -1
    port_count = 0
    rcv_max_interval = rcv_min_interval = None
    rcv_max_length = 0
    rcv_min_length = 65535
    snd_max_interval = snd_min_interval = None
    snd_max_length = 0
    snd_min_length = 65535
    label = None

    port_freq = {}
    last_rcv_time = last_snd_time = None

    for field in packets_in_flow.values():

        timestamp = float(field[0])
        direction = field[1]
        proto = field[2]
        port = int(field[3])
        length = field[5]

        if direction == "rcv":

            # --- rcv_count
            rcv_packet_count += 1

            # --- rcv_max/min_interval
            if last_rcv_time is not None:
                rcv_interval = timestamp - last_rcv_time
                if rcv_max_interval is None or rcv_max_interval < rcv_interval:
                    rcv_max_interval = rcv_interval
                if rcv_min_interval is None or rcv_max_interval > rcv_interval:
                    rcv_min_interval = rcv_interval
            last_rcv_time = timestamp

            # --- rcv_max/min_length
            rcv_length = length
            if rcv_max_length is None or rcv_length > rcv_max_length:
                rcv_max_length = rcv_length
            if rcv_min_length is None or rcv_length < rcv_min_length:
                rcv_min_length = rcv_length

            # --- most port / port count
            if port in port_freq:
                port_freq[port] += 1
            else:
                port_freq[port] = 1
            if port_freq[port] > port_count:
                most_port = port
                port_count = port_freq[port]

        elif direction == "snd":
            
            # --- snd_count
            snd_packet_count += 1

            # --- snd_max/min_interval
            if last_snd_time is not None:
                snd_interval = timestamp - last_snd_time
                if snd_max_interval is None or snd_interval > snd_max_interval:
                    snd_max_interval = snd_interval
                if snd_min_interval is None or snd_interval < snd_min_interval:
                    snd_min_interval = snd_interval
            last_snd_time = timestamp

            # --- rcv_max/min_length
            snd_length = length
            if snd_length > snd_max_length:
                snd_max_length = snd_length
            if snd_length < snd_min_length:
                snd_min_length = snd_length

        # --- tcp/udp count
        if proto == "tcp":
            tcp_count += 1
        elif proto == "udp":
            udp_count += 1

        # --- label
        if label is None:
            label = field[6]
    

    rcv_max_interval = rcv_max_interval if rcv_max_interval is not None else 60 # FLOW_TIMEOUTとこの値は一致させる
    rcv_min_interval = rcv_min_interval if rcv_min_interval is not None else 60
    rcv_min_length = rcv_min_length if rcv_min_length != 65535 else -10000
    snd_max_interval = snd_max_interval if snd_max_interval is not None else 60
    snd_min_interval = snd_min_interval if snd_min_interval is not None else 60
    snd_min_length = snd_min_length if snd_min_length != 65535 else -10000

    return [
        rcv_packet_count,
        snd_packet_count,
        tcp_count,
        udp_count,
        most_port,
        port_count,
        rcv_max_interval,
        rcv_min_interval,
        rcv_max_length,
        rcv_min_length,
        snd_max_interval,
        snd_min_interval,
        snd_max_length,
        snd_min_length,
        label
    ]


class FlowManager:

    def __init__(self, eal, mas, bas, ft):

        self.ex_address_list = eal
        self.malicious_address_set = mas
        self.benign_address_set = bas
        self.flow_timeout = ft
        self.first_row_dtime = None
        # flow_manager = {
        #     (Flow registered time(unix epoc time), "External_Address", "Internal_Address"): {
        #         1st seq: [Packet registered time(unix epoc time), direction, protocol, port, tcp_flag, length, label],
        #         2nd seq: [Packet registered time(unix epoc time), direction, protocol, port, tcp_flag, length, label],
        #         3rd seq: [Packet registered time(unix epoc time), direction, protocol, port, tcp_flag, length, label],
        #         >>>
        #         Nth seq: [Packet registered time(unix epoc time), direction, protocol, port, tcp_flag, length, label]
        #     },
        #     (1659513007.736493, '192.168.10.5', '187.35.147.87'): {
        #         1: ['rcv', 'tcp', '22', 'PA', '136', '1'],
        #         2: ['snd', 'udp', '22', 'PA', '136', '1'],
        #     }
        # }
        self.seq = 0
        self.flow_manager = dict()
        self.featured_flow_matrix = [[
            "ex_address",
            "in_address",
            "daytime",
            "rcv_packet_count",
            "snd_packet_count",
            "tcp_count",
            "udp_count",
            "most_port",
            "port_count",
            "rcv_max_interval",
            "rcv_min_interval",
            "rcv_max_length",
            "rcv_min_length",
            "snd_max_interval",
            "snd_min_interval",
            "snd_max_length",
            "snd_min_length",
            "label"
        ]]

    def delete_flow(self, key):  # flow_boxからフローを削除
        flow = self.flow_manager.pop(key)
        flow_begin_timestamp = datetime.fromtimestamp(key[0], timezone.utc)
        js = timezone(timedelta(hours=9))
        flow_daytime_jst = flow_begin_timestamp.astimezone(js)  # jst-utc間時差9時間
        flow_daytime_str = flow_daytime_jst.strftime("%Y-%m-%d %H:%M:%S")
        featured_list = [key[1], key[2], flow_daytime_str]
        featured_list.extend(extract_features_from_flow(flow))
        self.featured_flow_matrix.append(featured_list)

    def is_flow_exist(self, captured_time, src, dst):
        if not self.flow_manager:
            return None
        else:
            # --- タイムアウトのフローは存在しているか？
            keys = list(self.flow_manager.keys())

            for key in keys:
                if captured_time - key[0] > self.flow_timeout:
                    self.delete_flow(key)

            keys = list(self.flow_manager.keys())
            for key in keys:
                if (key[1] == src and key[2] == dst) or (key[1] == dst and key[2] == src):
                    return key  # if exist return key
            return None

    def callback(self, pkt):
        # time.sleep(3)
        # print(self.flow_manager)
        self.seq += 1 # パケット識別子
        captured_time = float(pkt.time)
        src = pkt[IP].src
        dst = pkt[IP].dst
        if self.first_row_dtime == None:
            frd_datetime = datetime.fromtimestamp(captured_time, timezone.utc)  # UTCのdatetimeオブジェクト
            js = timezone(timedelta(hours=9))  # JSTのタイムゾーン
            frd_dtime_jst = frd_datetime.astimezone(js)  # JSTに変換
            self.first_row_dtime = frd_dtime_jst.strftime("%Y%m%d%H%M%S")  # フォーマット済み文字列を設定

        addr,field = extract_features_from_packet(pkt, self.malicious_address_set,
                                                   self.benign_address_set)
        key = self.is_flow_exist(captured_time, src, dst)
        if field is not None:
            if key is None:
                new_flow_key = (captured_time, addr[0], addr[1])
                self.flow_manager[new_flow_key] = {f"{self.seq:08d}": field}
            else:
                self.flow_manager[key][f"{self.seq:08d}"] = field


def online(manager, filter_online):
    print("online mode")
    while 1:
        sniff(prn=manager.callback, timeout=capture_timeout, store=False, filter=filter_online)


def offline(file_path, manager, filter_offline):
    if os.path.getsize(file_path) == 0:
        print(os.path.basename(file_path) + ":no data")
    else:
        sniff(offline=file_path, prn=manager.callback, store=False, filter=filter_offline)
        print(os.path.basename(file_path) + ":finish")


def process_pcap_file(pcap_file_path, outputs_dir_path, external_addr_list, malicious_addresses, benign_addresses,
                      timeout, c_filter, count):
    # 各タスクごとに新しいFlowManagerインスタンスを生成
    manager = FlowManager(external_addr_list, malicious_addresses, benign_addresses, timeout)

    # ファイルのオフライン解析を実行
    offline(pcap_file_path, manager, c_filter)

    # 結果の書き出し
    feature_matrix_column = manager.featured_flow_matrix[0]
    feature_matrix_row = manager.featured_flow_matrix[1:]
    feature_matrix = pd.DataFrame(feature_matrix_row, columns=feature_matrix_column)
    feature_matrix.to_csv(f"{outputs_dir_path}/{manager.first_row_dtime}.csv",
                          index=False)
    return count  # 処理が完了したカウント番号を返す

# 与えられたフォルダまたはファイルに含まれるトラヒックデータ（pcapファイル）から特徴量を抽出してcsvファイルに書き込む
if __name__ == "__main__":

    start_time = time.time()  # 処理開始時刻

    # --- Load settings
    settings = json.load(open('src/main/FE_settings.json', 'r'))

    # --- Get current time in JST
    jst = pytz.timezone("Asia/Tokyo")
    init_time: str = datetime.now(jst).strftime("%Y%m%d%H%M%S")

    # --- Field
    online_mode = settings["ONLINE_MODE"]
    traffic_data_path = settings["TRAFFIC_DATA_PATH"]
    second_dir = traffic_data_path.split("/")[2]

    flow_timeout = settings["FLOW_TIMEOUT"]  # connection timeout [seconds]
    capture_timeout = settings["CAPTURE_TIMEOUT"]
    max_worker = settings["MAX_WORKER"]

    malicious_network_address_list = settings["NetworkAddress"][second_dir]["MALICIOUS"]
    malicious_address_set = set()
    for net in malicious_network_address_list:
        for malicious in ipaddress.ip_network(net):
            malicious_address_set.add(str(malicious))

    benign_network_address_list = settings["NetworkAddress"][second_dir]["BENIGN"]
    benign_address_set = set()
    for net in benign_network_address_list:
        for benign in ipaddress.ip_network(net):
            benign_address_set.add(str(benign))

    ex_addr_list = settings["NetworkAddress"][second_dir]["EXCEPTION"]
    ex_addr_set = set()
    for net in ex_addr_list:
        for ex_addr in ipaddress.ip_network(net):
            ex_addr_set.add(str(ex_addr))
    ex_addr_filter = " and ".join([f"not (ip src {ip} or ip dst {ip})" for ip in ex_addr_set])
    filter_condition = f"ether proto 0x0800 and ({ex_addr_filter}) and (tcp or udp)"

    # --- Create output directory for csv
    outputs_path: str = f"data/csv/unproc/{init_time}-{os.path.basename(traffic_data_path)}"
    os.makedirs(outputs_path)
    
    # --- build constructor
    flow_manager = FlowManager(ex_addr_list, malicious_address_set, benign_address_set, flow_timeout)
    
    # --- Online mode
    if online_mode:
        online(flow_manager, filter_condition)
    # --- Offline mode
    elif os.path.isdir(traffic_data_path):
        print("offline mode sniffing ...")
        pcap_files = []
        for root, _, files in os.walk(traffic_data_path):
            for file in files:
                full_path = os.path.join(root, file)
                pcap_files.append(full_path)
        
        pcap_files = sorted(pcap_files)
        
        with ProcessPoolExecutor(max_workers=max_worker) as executor:
            futures = [
                executor.submit(process_pcap_file,
                                pcap_file,
                                outputs_path,
                                ex_addr_list,
                                malicious_address_set,
                                benign_address_set,
                                flow_timeout,
                                filter_condition,
                                count)
                for count, pcap_file in enumerate(pcap_files)
            ]
            for count, future in enumerate(futures, start=1):
                try:
                    print(f"Completed processing {future.result()}/{len(pcap_files)}")
                except Exception as e:
                    print(f"Error processing file {count}: {e}")


                    
