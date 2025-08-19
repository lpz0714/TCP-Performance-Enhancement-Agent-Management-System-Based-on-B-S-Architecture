from flask import Flask, render_template, request, jsonify
import threading
import json
import os
from mininet.net import Mininet
from mininet.node import Node, Controller, RemoteController
from mininet.link import TCLink
from mininet.topo import Topo
from mininet.cli import CLI
from mininet.log import info, setLogLevel
import importlib.util
import subprocess

app = Flask(__name__)

CONFIG_FILE = "pep_config.json"

# PEP脚本路径
PEP_SCRIPTS = {
    "B": "/home/mininet/pepesc/pepesc-main/Mininet-scripts/nodeB_pep.sh",
    "C": "/home/mininet/pepesc/pepesc-main/Mininet-scripts/nodeC_pep.sh"
}

# 全局变量存储Mininet网络实例
net = None

# 默认配置
DEFAULT_CONFIG = {
    "B": {
        "self_ip": "10.0.1.2",
        "self_port": 9999,
        "peer_ip": "10.0.1.3",
        "peer_port": 9999,
    },
    "C": {
        "self_ip": "10.0.1.3",
        "self_port": 9999,
        "peer_ip": "10.0.1.2",
        "peer_port": 9999,
    }
}

def get_mininet_network():
    """获取当前运行的Mininet网络实例"""
    global net
    if net is None:
        try:
            # 导入4_nodes_topo.py模块
            topo_path = "/home/mininet/pepesc/pepesc-main/Mininet-scripts/4_nodes_topo.py"
            spec = importlib.util.spec_from_file_location("topo", topo_path)
            topo_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(topo_module)
            
            # 获取网络实例
            net = topo_module.net
            if net is None:
                raise Exception("无法获取Mininet网络实例")
        except Exception as e:
            raise Exception(f"加载拓扑文件失败: {e}")
    return net

PEP_STATUS = {
    "B": {"status": "stopped", "msg": "等待操作...", "thread": None},
    "C": {"status": "stopped", "msg": "等待操作...", "thread": None}
}

def get_node_pid(node_name):
    result = subprocess.check_output(f"pgrep -f 'mininet:{node_name}'", shell=True)
    return int(result.decode().strip().split('\n')[0])

def run_pep(node_key):
    status = PEP_STATUS[node_key]
    try:
        node_name = f'node{node_key}'
        pid = get_node_pid(node_name)
        script = PEP_SCRIPTS[node_key]
        cmd = f"mnexec -a {pid} sh {script}"
        subprocess.Popen(cmd, shell=True)
        status["status"] = "running"
        if status.get("restarted"):
            status["msg"] = "已重启，PEP成功运行"
            status["restarted"] = False
        else:
            status["msg"] = "PEP成功运行"
    except Exception as e:
        status["status"] = "stopped"
        status["msg"] = f"启动失败: {e}"

def stop_pep(node_key):
    status = PEP_STATUS[node_key]
    try:
        node_name = f'node{node_key}'
        pid = get_node_pid(node_name)
        cmd = f"mnexec -a {pid} pkill -f pep.py"
        subprocess.Popen(cmd, shell=True)
        status["status"] = "stopped"
        status["msg"] = "PEP成功关闭"
    except Exception as e:
        status["msg"] = f"停止失败: {e}"

@app.route('/')
def index():
    return render_template('index.html', nodes=NODES_CONFIG, pep_status=PEP_STATUS)

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({k: {"status": v["status"], "msg": v["msg"]} for k, v in PEP_STATUS.items()})

@app.route('/api/start', methods=['POST'])
def start_pep():
    for node_key in ["B", "C"]:
        if PEP_STATUS[node_key]["status"] == "running":
            continue
        PEP_STATUS[node_key]["status"] = "starting"
        PEP_STATUS[node_key]["msg"] = "正在启动..."
        t = threading.Thread(target=run_pep, args=(node_key,))
        PEP_STATUS[node_key]["thread"] = t
        t.start()
    return jsonify({"success": True})

@app.route('/api/stop', methods=['POST'])
def stop_pep_api():
    for node_key in ["B", "C"]:
        stop_pep(node_key)
    return jsonify({"success": True})

@app.route('/api/restart', methods=['POST'])
def restart_pep():
    for node_key in ["B", "C"]:
        stop_pep(node_key)
        PEP_STATUS[node_key]["status"] = "starting"
        PEP_STATUS[node_key]["msg"] = "正在重启..."
        PEP_STATUS[node_key]["restarted"] = True
        t = threading.Thread(target=run_pep, args=(node_key,))
        PEP_STATUS[node_key]["thread"] = t
        t.start()
    return jsonify({"success": True})

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return DEFAULT_CONFIG.copy()

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

# 启动时加载配置
NODES_CONFIG = load_config()

@app.route('/api/get_config', methods=['GET'])
def get_pep_config():
    return jsonify(NODES_CONFIG)

@app.route('/api/save_config', methods=['POST'])
def save_pep_config():
    data = request.json
    for node_key in ["B", "C"]:
        for k in ["self_ip", "self_port", "peer_ip", "peer_port"]:
            NODES_CONFIG[node_key][k] = data[node_key][k]
    save_config(NODES_CONFIG)
    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

