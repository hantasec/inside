import os
import sys
import time
import paramiko
from netmiko import ConnectHandler

path = "./setting"
dev_path = path+"/devinfo"
backup_path = path + "/backup"
ip_path = path + "/ip"
route_path = path + "/route"


dev_type = {
    '1' : "router",
    '2' : "switch",
    '3' : "rocky",
    '4' : 'ubuntu'
}

def device_replace(types, name, dev_data):
    file_path = "%s/%s_device.txt" % (dev_path, types)

    with open(file_path, 'r', encoding='utf-8') as devinfo:
        lines = devinfo.readlines()

    with open(file_path, 'w', encoding='utf-8') as devinfo:
        for line in lines:
            info = line.split()

            if info[1] == name:
                devinfo.write(dev_data)
            else:
                devinfo.write(line)

    print(dev_data)
    print("%s/%s_device.txt 의 장치 정보가 변경되었습니다." % (dev_path, types))

def device_append(types, dev_data):
    with open("%s/%s_device.txt" % (dev_path, types), 'a', encoding='utf-8') as devinfo:
        devinfo.write(dev_data)

    print(dev_data)
    print("%s/%s_device.txt 에 장치가 추가되었습니다." % (dev_path, types))

def t_create_dev_info():

    dup = 'new'

    select = input("장치의 종류를 선택하세요. [1.라우터] [2.스위치] [3.록키 리눅스] [4.우분투]\n:")

    if select not in dev_type:
        print("올바른 형식이 아님")
        return

    types = dev_type[select]
    os.makedirs(dev_path, exist_ok=True)

    name = input("장치명을 입력해 주세요.")

    file_path = "%s/%s_device.txt" % (dev_path, types)

    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                info = line.split()

                if info[1] == name:
                    dup = input("이미 존재하는 장치명입니다. 장치 정보를 변경하시겠습니까? y/n : ")
                    break

    if dup == 'n':
        print("설정을 취소합니다.")
        return

    host_ip = input("생성할 장비의 IP 주소를 입력하세요: ")
    username = input("생성할 장비의 계정 이름을 입력하세요: ")
    password = input("생성할 장비의 비밀번호를 입력하세요: ")

    dev_data = types + ' ' + name + ' ' + host_ip + ' ' + username + ' ' + password + '\n'

    if dup == 'y':
        device_replace(types, name, dev_data)
        return

    device_append(types, dev_data)

def t_select_dev() :
    
    device = []
    
    select = input("장치의 종류를 선택하세요. [1.라우터] [2.스위치] [3.록키 리눅스] [4.우분투]\n:")

    if select not in dev_type:
        print("올바른 형식이 아님")
        return

    types = dev_type[select]

    print("-----등록된 장치 리스트------")
   
    with open("%s/%s_device.txt"%(dev_path,types), 'r', encoding='utf-8') as dev_info : 
        dev_list = dev_info.readlines()
        for dev in dev_list :
            print(dev, end='')
        
        select = input("\n\n접속할 장치를 선택해 주세요 : ")
        for dev in dev_list :
            info = dev.strip().split()
            if info[1] == select :
                device = info
                break
    
    if not device :
        print("없는 계정입니다.")
        return
    else :
        return t_make_dict(device)
      
def t_make_dict(device):

    data = dict()

    if device[0] in ["router", "switch"]:

        data = {
            'types': device[0],
            'name': device[1],
            'device_type': 'cisco_ios',
            'host': device[2],
            'username': device[3],
            'password': device[4],
            'port': 22,
            'conn_timeout': 30,
            'auth_timeout': 30,
            'banner_timeout': 30
        }

    elif device[0] in ["rocky", "ubuntu"]:

        data = {
            'types': device[0],
            'name': device[1],
            'host': device[2],
            'username': device[3],
            'password': device[4],
            'port': 22,
        }

    return data

def connect_linux(device) :
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print("리눅스 서버에 연결 중...")

    cli.connect(
        hostname=device["host"],
        port=22,
        username=device["username"],
        password=device["password"],
        timeout=20
    )

    return cli

def connect_cisco(device_info):
    conn_info = device_info.copy()
    conn_info.pop("types", None)
    conn_info.pop("name", None)
    
    # 숫자형 데이터 변환
    conn_info["port"] = int(conn_info["port"])
    conn_info["conn_timeout"] = int(conn_info["conn_timeout"])
    conn_info["auth_timeout"] = int(conn_info["auth_timeout"])
    conn_info["banner_timeout"] = int(conn_info["banner_timeout"])

    print("%s 접속 시도 중 "%(conn_info["host"]))
    

    cli = ConnectHandler(**conn_info, global_delay_factor=2)
    cli.enable()
    return cli

def command_cisco(cli, command) :
    if isinstance(command, str):
        command = command.splitlines()
    output = cli.send_config_set(command)
    print(output)
    print("장비 설정 적용 완료!")
    return output


# cisco 백업 / 복원 처리 부분-----------------------------------------------

def cisco_backup(cli,device_info) :

    os.makedirs(backup_path, exist_ok=True)
    
    cmd = "show run"
    output = cli.send_command(cmd)
    
    with open("%s/%s_%s_backup.txt" %(backup_path,device_info["types"],device_info["name"]), "w") as file:
        file.write(output)
        
    print("백업 완료")

def cisco_restore(cli) :

    backup_list = os.listdir(backup_path)
    for i in range(len(backup_list)) :
        backup_list[i] = backup_list[i].replace(".txt","")
    print(backup_list)
    name = input("복구할 백업 파일명을 입력하세요. : ")

    file = open("%s/%s.txt" %(backup_path,name), "r", encoding="utf-8")
    lines = file.readlines()
    file.close()

    ether_cmd = []
    route_cmd = []

    for i in range(len(lines)):
        clear_line = lines[i].strip()

        if clear_line == "!" or clear_line == "":
            continue

        if clear_line.startswith("interface"):
            ether_cmd.append(clear_line)
            new_clear = lines[i + 1].strip()
            ether_cmd.append(new_clear)

        if clear_line.startswith("ip forward-protocol"):
            cnt = 1
            while True:
                new_clear_line = lines[i + cnt].strip()

                if new_clear_line.startswith("no ip http server"):
                    break

                route_cmd.append(new_clear_line)
                cnt += 1

    tot_cmd_lines = []
    tot_cmd_lines.extend(ether_cmd)
    tot_cmd_lines.extend(route_cmd)

    tot_cmd = "\n".join(tot_cmd_lines)

    command_cisco(cli,tot_cmd)

# cisco IP / Route 처리 부분-----------------------------------------------

def ip_preset() :
    cmd = ""
    os.makedirs(ip_path, exist_ok=True)
    name = input("생성할 ip셋의 이름 : ")
    while True :
        cmd += input("인터페이스\t: ")
        cmd += ' ' + input("네트워크\t: ")
        cmd += ' ' + input("서브넷\t: ") 
        cmd += '\n'
        if 'n' == input("계속? y/n") :
            break
    
    with open("%s/%s.txt"%(ip_path,name), "w") as file :
        file.write(cmd)

def ip_setting(cli) :
    command = ""
    ip_list = os.listdir(ip_path)
    for i in range(len(ip_list)) :
        ip_list[i] = ip_list[i].replace(".txt","")
    print(ip_list)
    name = input("인터페이스 일괄 등록 ip 파일명을 입력하세요. : ")

    with open("%s/%s.txt"%(ip_path,name), 'r') as f:
        lines = f.readlines()

        for ip in lines:
            ip = ip.strip()

            if not ip:
                continue

            interface, network, subnet = ip.split()

            command += (
                "int " + interface + "\n"
                + "ip add " + network + " " + subnet + "\n"
                + "no shut\n"
            )

        print("설정된 값\n" + command)
        command_cisco(cli,command)

def route_preset() :
    cmd = ""
    os.makedirs(route_path, exist_ok=True)
    name = input("생성할 route셋의 이름 : ")
    while True :
        cmd += input("목적지 네트워크\t: ")
        cmd += ' ' + input("서브넷\t: ")
        cmd += ' ' + input("게이트웨이\t: ")
        cmd += '\n'
        if 'n' == input("계속? y/n") :
            break
    
    with open("%s/%s.txt"%(route_path,name), "w") as file :
        file.write(cmd)

def route_setting(cli) :
    command = ""
    route_list = os.listdir(route_path)
    for i in range(len(route_list)) :
        route_list[i] = route_list[i].replace(".txt","")
    print(route_list)
    name = input("라우팅 경로 일괄 등록 라우트 파일명을 입력하세요. : ")

    with open("%s/%s.txt"%(route_path,name), 'r') as f:
        lines = f.readlines()

        for route in lines:
            route = route.strip()

            if not route:
                continue

            command += "ip route " + route + "\n"

        print("설정된 값\n" + command)
        command_cisco(cli,command)

def static_router_setting(cli) :
    ro_ip_str = input("ip대역 입력: ")
    ro_sub_str = input("서브넷마스크 입력: ")
    ro_gw_str = input("게이트웨이 입력: ")

    command = (
        "ip route "
        + ro_ip_str + " "
        + ro_sub_str + " "
        + ro_gw_str
    )

    output = command_cisco(cli, command)

# cisco NAT 처리 부분-----------------------------------------------

def nat_setting(cli):
    nat_menu = {
        "1": nat_static,
        "2": nat_dynamic,
        "3": pat
    }

    select = input("""NAT 종류를 선택하세요.
    1. Static NAT
    2. Dynamic NAT
    3. PAT
    선택: """)

    func = nat_menu.get(select)

    if func:
        func(cli)
    else:
        print("입력값이 올바르지 않습니다.")

def nat_static(cli) :
    outside_port_input = input("외부 망 포트 번호(예: e0/0, e1/0) : ").strip()
    inside_port_input = input("내부 망 포트 번호(예: e2/0, e2/1) : ").strip()
    local_ip_input = input("로컬 IP : ").strip()
    global_ip_input = input("공인 IP : ").strip()

    command_static = [
        "int " + outside_port_input,
        "ip nat outside",
        "exit",
        "int " + inside_port_input,
        "ip nat inside",
        "exit",
        "ip nat inside source static " + local_ip_input + " " + global_ip_input
    ]

    command_cisco(cli, command_static)

def nat_dynamic(cli) :
    outside_port_input = input("외부 망 포트 번호(예: e0/0, e1/0) : ")
    inside_port_input = input("내부 망 포트 번호(예: e2/0, e2/1) : ")

    inside_ip_input = input("내부 네트워크 IP : ")
    wildcardmask_input = input("와일드카드 마스크 예: 0.0.0.255 : ")
    first_global_ip = input("첫 번째 공인 IP : ")
    second_global_ip = input("마지막 공인 IP : ")
    subnetmask_input = input("서브넷 마스크 예: 255.255.255.0 : ")
    pool_input = input("pool name : ")

    command_dynamic = [
        "int " + outside_port_input,
        "ip nat outside",
        "exit",
        "int " + inside_port_input,
        "ip nat inside",
        "exit",
        "access-list 1 permit " + inside_ip_input + " " + wildcardmask_input,
        "ip nat pool " + pool_input + " " + first_global_ip + " " + second_global_ip + " netmask " + subnetmask_input,
        "ip nat inside source list 1 pool " + pool_input
    ]

    command_cisco(cli, command_dynamic)

def pat(cli) :
    outside_port_input = input("외부 망 포트 번호(예: e0/0, e1/0) : ")
    inside_port_input = input("내부 망 포트 번호(예: e2/0, e2/1) : ")

    inside_ip_input = input("내부 네트워크 IP : ")
    wildcardmask_input = input("와일드카드 마스크 예: 0.0.0.255 : ")
    first_global_ip = input("첫 번째 공인 IP : ")
    second_global_ip = input("마지막 공인 IP : ")
    subnetmask_input = input("서브넷 마스크 예: 255.255.255.0 : ")
    pool_input = input("pool name : ")

    command_pat = [
        "int " + outside_port_input,
        "ip nat outside",
        "exit",
        "int " + inside_port_input,
        "ip nat inside",
        "exit",
        "access-list 1 permit " + inside_ip_input + " " + wildcardmask_input,
        "ip nat pool " + pool_input + " " + first_global_ip + " " + second_global_ip + " netmask " + subnetmask_input,
        "ip nat inside source list 1 pool " + pool_input + " overload"
    ]

    command_cisco(cli, command_pat)

# cisco DHCP / SVI 처리 부분-----------------------------------------------

def dhcp_setting(cli) :
    name = input("DHCP 풀 이름: ")
    network = input("네트워크 대역과 마스크: ")
    gateway = input("디폴트 라우터: ")
    dns = input("DNS 서버: ")
    exclude = input("예외 주소 대역: ")

    command = (
        "ip dhcp excluded-address " + exclude + "\n"
        + "ip dhcp pool " + name + "\n"
        + "network " + network + "\n"
        + "default-router " + gateway + "\n"
        + "dns-server " + dns + "\n"
        + "exit\n"
    )

    print("설정된 값\n" + command)
    command_cisco(cli, command)

def svi_setting(cli) :
    vlan_id = input("VLAN id 번호 입력: ")
    ip = input("SVI IP 주소 입력: ")
    subnet = input("서브넷 마스크 입력: ")

    command = (
        "vlan " + vlan_id + "\n"
        + "interface vlan " + vlan_id + "\n"
        + "ip address " + ip + " " + subnet + "\n"
        + "no shut\n"
    )

    print("설정된 값\n" + command)
    command_cisco(cli, command)
    print("SVI 설정 적용 완료!")

def cisco_menu(device_info) :
    cli = connect_cisco(device_info)
    
    menu = {
        "1": cisco_backup,
        "2": cisco_restore,
        "3": ip_setting,
        "4": ip_preset,
        "5": route_setting,
        "6": route_preset,
        "7": static_router_setting,
        "8": nat_setting,
        "9": dhcp_setting,
        "10": svi_setting
    }
    
    while True :
        select = input("""작업을 선택하세요.\n
        1. 장치 세팅값 백업
        2. 세팅 전체 복원
        3. 인터페이스 IP 일괄설정 (파일)
        4. 인터페이스 IP 프리셋 등록
        5. Route 일괄등록 (파일)  
        6. Route 프리셋 등록
        7. Route 개별 등록
        8. NAT
        9. DHCP 설정
        10. SVI 설정
        0. 설정 종료
        선택: """)

        if select == "0":
            cli.disconnect()
            break
        
        elif select not in menu :
            print("잘못된 입력입니다. 번호를 다시 입력해 주세요.")
            continue
        
        func = menu.get(select)

        if select == "1":
            func(cli, device_info)

        elif select in ["4", "6"]:
            func()        
        
        else:
            func(cli)

# rocky linux ip,gateway 처리 부분-----------------------------------------------

def roc_ip_set(cli, device_info):

    ens = input("설정할 인터페이스를 입력하세요.(ex:ens160):")

    restart = (
        "nmcli connection down " + ens +
        " ; nmcli connection up " + ens
    )

    ipsetting = input("설정할 아이피 주소를 입력하세요:")
    fixsetting = input("설정할 프리픽스를 입력하세요(예:/16):")

    cli.exec_command(
        "nmcli connection modify "
        + ens +
        " ipv4.addresses "
        + ipsetting + fixsetting
    )

    # device_info 내부 IP 갱신
    device_info['host'] = ipsetting

    # 저장용 문자열 생성
    dev_data = (
        device_info['types'] + ' ' +
        device_info['name'] + ' ' +
        device_info['host'] + ' ' +
        device_info['username'] + ' ' +
        device_info['password'] + '\n'
    )

    # 파일 정보 수정
    device_replace(
        device_info['types'],
        device_info['name'],
        dev_data
    )

    print("IP가 변경됩니다... 프로그램이 종료됩니다.")

    cli.exec_command(restart)
    cli.close()
    sys.exit()

def roc_gate_set(cli, device_info):

    ens = input("설정할 인터페이스를 입력하세요.(ex:ens160):")

    restart = (
        "nmcli connection down " + ens +
        " ; nmcli connection up " + ens
    )

    gatesetting = input("설정할 게이트웨이 주소를 입력하세요:")

    stdin, stdout, stderr = cli.exec_command(
        "nmcli connection modify "
        + ens +
        " ipv4.gateway "
        + gatesetting
    )

    print("gateway가 변경됩니다... 프로그램이 종료됩니다.")

    stdin, stdout, stderr = cli.exec_command(restart)

    cli.close()

    sys.exit()

# rocky 명령 선택 부분-----------------------------------------------

def roc_select() :
    
    select = int(input(""" 
    실행할 작업의 번호 선택하세요.
    1. 방화벽 해제
    2. 패키지 업데이트
    3. 패키지 세팅(wget, vim, libstdc++, tar, gzip)
    4. 미니콘다 설치
    5. 주피터 노트북 실행 설정
    6. systempython, 파라미코 설치
    7. 록키리눅스 ip 변경(종료됨!)
    8. 록키리눅스 gateway 변경(종료됨!)
    0. 종료
    선택: """))

    if select not in range(0,9):
        print("잘못된 선택입니다.")
        return None

    if select == 0:
        print("프로그램을 종료합니다.")
        return 0
    
    return select

def roc_run(cli, select, device_info):
    
    firewall_meth = [
        "systemctl disable --now firewalld",
        "sed -i 's/^SELINUX=enforcing/SELINUX=disabled/' /etc/selinux/config",
        "setenforce 0",
        "init 6"
    ]

    package_update_meth = [
        "dnf -y update && dnf -y upgrade"
    ]

    package_setting_meth = [
        "dnf -y install epel-release wget vim libstdc++ tar gzip expect",
        "dnf makecache",
        "dnf config-manager --set-enabled crb",
        "dnf -y update && dnf -y upgrade"
    ]

    miniconda_meth = [
        "wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh",
        "chmod u+x Miniconda3-latest-Linux-x86_64.sh",
        "./Miniconda3-latest-Linux-x86_64.sh -b",
        "sed -i '$a export PATH=$PATH:/root/miniconda3/bin' /etc/bashrc",
        "/root/miniconda3/bin/conda config --set auto_activate false",
        "/root/miniconda3/bin/conda tos accept --override-channels --channel \"https://repo.anaconda.com/pkgs/main\"",
        "/root/miniconda3/bin/conda tos accept --override-channels --channel \"https://repo.anaconda.com/pkgs/r\"",
        "/root/miniconda3/bin/conda install jupyter -y"
    ]

    jupyternotebook_meth = [
        "expect -c 'spawn /root/miniconda3/bin/jupyter notebook password; expect \"Enter password:\"; send \"asd123!@\\r\"; expect \"Verify password:\"; send \"asd123!@\\r\"; expect eof'",
        "mkdir -p /opt/just_serv",
        "printf '#!/bin/bash\n/root/miniconda3/bin/jupyter notebook --allow-root --ip=0.0.0.0 --port=8080 --no-browser\n' > /opt/just_serv/just.sh",
        "chmod +x /opt/just_serv/just.sh",
        "printf '[Unit]\nDescription=Jupyter notebook start service\nAfter=network.target\n\n[Service]\nType=simple\nEnvironment=\"PATH=/root/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin\"\nExecStart=/opt/just_serv/just.sh\nRestart=always\nRestartSec=5s\n\n[Install]\nWantedBy=multi-user.target\n' > /etc/systemd/system/just.service",
        "systemctl daemon-reload",
        "systemctl enable just.service",
        "systemctl restart just.service",
        "systemctl status just.service --no-pager"
    ]
    #넷미코 추가.
    pythonsystem_paramico_meth = [
        "/root/miniconda3/bin/conda install pip -y",
        "/root/miniconda3/bin/pip install --upgrade pip",
        "/root/miniconda3/bin/pip install paramiko",
        "/root/miniconda3/bin/conda install -y -c conda-forge types-cryptography",
        "/root/miniconda3/bin/python3 -m pip install ipykernel",
        "/root/miniconda3/bin/python3 -m ipykernel install --user --name system-python --display-name \"Python 3 (System)\"",
        "/root/miniconda3/bin/pip install netmiko"
    ]

    cmd_dict = {
            1: firewall_meth,
            2: package_update_meth,
            3: package_setting_meth,
            4: miniconda_meth,
            5: jupyternotebook_meth,
            6: pythonsystem_paramico_meth,
            7: roc_ip_set,
            8: roc_gate_set,
            0: 0
    }
    
    if select in range(1,7):
        cmd = cmd_dict[select]
        for i in cmd:
            print("-> 실행 중: %s" % i)

            if i == "init 6":
                print("시스템을 재부팅합니다. 연결이 끊어집니다.")
                cli.exec_command(i)
                time.sleep(2)
                break

            stdin, stdout, stderr = cli.exec_command(i)

            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()

            if error:
                print("[알림/에러] %s" % error)

            if output:
                print("[결과] %s" % output)
    else :
        func = cmd_dict[select]
        if func :
            func(cli, device_info)
        else :
            print("함수 실행이 안되는데요??")

def roc_menu(device_info) :
    cli = connect_linux(device_info)
    if cli is None:
        print("리눅스 연결 실패로 메뉴를 종료합니다.")
        return
    
    while True :
        select = roc_select()

        if select is None:
            continue

        if select == 0 :
            print("exit")
            break

        roc_run(cli, select, device_info)


    cli.close()


# 우분투 yaml 설정 ----------------------------------------------

def ubt_create_dhcp_yaml(interface):
    yaml_content = f"""network:
  version: 2
  renderer: networkd
  ethernets:
    {interface}:
      dhcp4: true
"""
    return yaml_content

def ubt_create_static_yaml(interface):
    ip_addr = input("할당할 IP/서브넷(예: 192.168.1.100/24): ")
    gateway = input("게이트웨이(예: 192.168.1.1): ")
    dns = "8.8.8.8"
    
    yaml_content = f"""network:
  version: 2
  renderer: networkd
  ethernets:
    {interface}:
      addresses:
        - {ip_addr}
      routes:
        - to: default
          via: {gateway}
      nameservers:
        addresses: [{dns}]
      dhcp4: false
"""
    return yaml_content

def ubt_package_check_install(cli, shell):
    cmd = input("확인 필요한 패키지명 입력: ")

    check_cmd = "dpkg -l | grep -w " + cmd

    stdin, stdout, stderr = cli.exec_command(check_cmd)
    check_res = stdout.readlines()

    if check_res:
        print("'%s' 패키지가 이미 설치되어 있습니다:" % cmd)
        for line in check_res:
            print(line.strip())
        return

    print("'%s' 패키지가 설치되어 있지 않습니다." % cmd)
    answer = input("'%s'을(를) 설치하시겠습니까? (y/n): " % cmd).lower()

    if answer == "y":
        print("설치를 시작합니다.")

        install_cmd = "apt-get update && apt-get install -y " + cmd
        stdin, stdout, stderr = cli.exec_command(install_cmd)

        output = stdout.read().decode("utf-8").strip()
        error = stderr.read().decode("utf-8").strip()

        if output:
            print("[결과] %s" % output)

        if error:
            print("[알림/에러] %s" % error)

        final_cmd = "dpkg -l | grep -w " + cmd
        stdin, stdout, stderr = cli.exec_command(final_cmd)
        final_check = stdout.readlines()

        if final_check:
            print("'%s' 설치가 완료되었습니다." % cmd)
            for line in final_check:
                print(line.strip())
        else:
            print("설치를 시도했으나 실패했습니다. 패키지명을 다시 확인해주세요.")

    else:
        print("설치를 취소했습니다.")

# ip a 백업    
def ubt_ip_a(output):
    file = open("ub_ip_a", "w", encoding = "utf-8")
    file.write(output)
    file.close()
    
#ip r 백업
def ubt_ip_r(output):
    file = open("ub_ip_r", "w", encoding = "utf-8")
    file.write(output)
    file.close()
# yaml 파일명 보여주고 어떤 파일 보여줄 지 .
def ubt_yaml_cat(cli, shell):

    for i in range(len(yaml)):
        print("%d. %s"%(i+1,yaml[i]))

    global y_num

    y_num = int(input("파일을 선택해주세요 : "))

    yaml_cat = "cat /etc/netplan/" + yaml[y_num-1]

    shell.send(yaml_cat + "\n")

    time.sleep(1)

    if shell.recv_ready():
        output = shell.recv(65535).decode('utf-8')
        print(output)

        ubt_make_yaml_cat(output)

# yaml 안에 있는 내용을 netplan 장비명, 한줄 띄고 아웃풋 입력 -> 네트워크 장치 정보 입력
def ubt_make_yaml_cat(output):
    file = open("netplan_cat", "w", encoding = "utf-8")
    data = yaml[y_num] +"\n"+ output
    file.write(data)
    file.close()

def ubt_netplan_list_meth(output):
    file = open("netplan_ls", "w", encoding = "utf-8")
    file.write(output)
    file.close()

    file = open("netplan_ls", "r", encoding = "utf-8")
    global yaml
    yaml = file.read().split()
    file.close()

def ubt_show_menu():
    res = int(input(""" 
    실행할 작업의 번호 선택하세요.
    1. 방화벽 해제
    2. 패키지 업데이트
    3. 패키지 세팅(wget, vim, libstdc++, tar, gzip)
    4. 미니콘다 설치
    5. 주피터 노트북 실행 설정
    6. systempython, 파라미코 설치
    7. dhcp ip 자동할당   ???
    8. netplan ip 수동 변환 및 할당   ???
    9. netplan 디렉토리 yaml 파일 리스트 쥬피터에 갱신
    10. yaml 파일 내용 파일 생성
    11. ip a
    12. ip r
    13. 패키지 확인 및 설치
    0. 종료
    선택: """))
    return res

# 우분투 쉘 명령어 전송
def ubt_send_shell_cmd(shell, cmd):

    print("-> 실행 중: %s" % cmd)

    shell.send(cmd + "\n")

    time.sleep(1)

    output = ""

    if shell.recv_ready():
        output = shell.recv(65535).decode('utf-8')
        print("[결과]\n%s" % output)

    return output
# 우분투 출력값 처리
def ubt_output_parser(cmd, output):

    if cmd == 9:
        ubt_netplan_list_meth(output)

    elif cmd == 11:
        ubt_ip_a(output)

    elif cmd == 12:
        ubt_ip_r(output)
# 넷플랜 설정
def ubt_set_netplan(shell, mode):

    shell.send("ip -o link show | awk -F': ' '{print $2}' | grep -v 'lo' | head -n1\n")
    time.sleep(1)

    interface = shell.recv(1024).decode().split('\n')[1].strip()
    shell.send("ls /etc/netplan/\n")
    time.sleep(1)

    files = shell.recv(1024).decode().split()
    target_file = [f for f in files if f.endswith('.yaml')][0]

    if mode == "dhcp":
        new_yaml = ubt_create_dhcp_yaml(interface)
        print("%s 네트워크를 DHCP로 전환합니다." % interface)

    elif mode == "static":
        new_yaml = ubt_create_static_yaml(interface)
        print("%s 네트워크를 정적 IP로 전환합니다." % interface)

    setup_cmd = (
        "cat <<EOF > /etc/netplan/%s\n" % target_file
        + new_yaml +
        "EOF\n"
    )

    shell.send(setup_cmd)
    time.sleep(1)
    shell.send("netplan apply\n")
    time.sleep(2)
    print("netplan apply가 실행되었습니다.")

def ubt_set_dhcp(cli, shell):

    ubt_set_netplan(shell, "dhcp")

def ubt_set_static(cli, shell):

    ubt_set_netplan(shell, "static")

# 우분투 작동부
def ubt_run_cmd(cli, shell, cmd):

    firewall_meth = [
        "systemctl disable --now ufw",
        "systemctl status ufw",
        "init 6"
    ]

    package_update_meth = [
        "apt-get update && apt-get -y upgrade"
    ]

    package_setting_meth = [
        "apt-get update",
        "apt-get -y install software-properties-common wget vim libstdc++6 tar gzip build-essential",
        "apt-get -y update && apt-get -y upgrade"
    ]

    miniconda_meth = [
        "wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh",
        "chmod u+x Miniconda3-latest-Linux-x86_64.sh",
        "./Miniconda3-latest-Linux-x86_64.sh -b -p /root/miniconda3",
        "sed -i '$a export PATH=$PATH:/root/miniconda3/bin' /etc/bash.bashrc",
        "/root/miniconda3/bin/conda config --set auto_activate false",
        "/root/miniconda3/bin/conda config --add channels defaults",
        "/root/miniconda3/bin/conda install jupyter -y"
    ]

    jupyternotebook_meth = [
        "apt-get install -y expect",

        "expect -c 'spawn /root/miniconda3/bin/jupyter notebook password; expect \"Enter password:\"; send \"asd123!@\\r\"; expect \"Verify password:\"; send \"asd123!@\\r\"; expect eof'",

        "echo \"#!/bin/bash\" > /root/jupyter_start.sh",

        "echo \"/root/miniconda3/bin/python3 -m jupyter notebook --allow-root --ip=0.0.0.0 --port=8080 --no-browser &\" >> /root/jupyter_start.sh",

        "chmod +x /root/jupyter_start.sh",

        "./jupyter_start.sh"
    ]

    pythonsystem_paramico_meth = [
        "/root/miniconda3/bin/conda install pip -y",
        "/root/miniconda3/bin/pip install --upgrade pip",
        "/root/miniconda3/bin/pip install paramiko",
        "/root/miniconda3/bin/conda install -y -c conda-forge types-cryptography",
        "/root/miniconda3/bin/python3 -m pip install ipykernel",
        "/root/miniconda3/bin/python3 -m ipykernel install --user --name system-python --display-name \"Python 3 (System)\""
    ]

    netplan_ls = [
        "ls /etc/netplan"
    ]

    ub_ip_a = [
        "ip a"
    ]

    ub_ip_r = [
        "ip r"
    ]

    cmd_dict = {
        1: firewall_meth,
        2: package_update_meth,
        3: package_setting_meth,
        4: miniconda_meth,
        5: jupyternotebook_meth,
        6: pythonsystem_paramico_meth,
        9: netplan_ls,
        11: ub_ip_a,
        12: ub_ip_r,
    }

    func_dict = {
        7: ubt_set_dhcp,
        8: ubt_set_static,
        10: ubt_yaml_cat,
        13: ubt_package_check_install,
    }

    if cmd not in cmd_dict and cmd not in func_dict:
        print("올바른 메뉴 번호가 아닙니다.")
        return
    
    # 특수 기능 함수 실행
    if cmd in func_dict:
        func_dict[cmd](cli, shell)
        return

    # 일반 명령어 실행
    output = ""

    for i in cmd_dict[cmd]:

        output = ubt_send_shell_cmd(shell, i)

        if i == "init 6":
            print("시스템을 재부팅합니다. 연결이 끊어집니다.")
            cli.close()
            break

    # 출력 후처리
    ubt_output_parser(cmd, output)

def ubt_menu(device_info) :
    cli = connect_linux(device_info)

    if cli is None:
        print("리눅스 연결 실패로 메뉴를 종료합니다.")
        return

    shell = cli.invoke_shell()
    time.sleep(1)

    
    while True :
        select = int(ubt_show_menu())

        if select not in range(0,14):
            print("입력 범위를 벗어났습니다. 다시 입력해 주세요.")
            continue

        elif select == 0 :
            print("exit")
            break

        else :
            ubt_run_cmd(cli,shell,select)

    cli.close()
# 연결 설립    
def connect_dev() :
    device = t_select_dev()

    if device is None:
        return
    
    print("%s %s 장치에 접속중입니다..." % (device["types"], device["name"]))       
    
    dev_menu = {
        "router":cisco_menu,
        "switch":cisco_menu,
        "rocky":roc_menu,
        "ubuntu":ubt_menu,
    }    

    func = dev_menu.get(device["types"])

    if func :
        func(device)   # dev_memu 에서 선택된 함수 실행하기.
    else :
        print("지원하지 않는 장비 타입입니다.")
        return    

#메인 함수
def main() :
    while True:
        a = input("[1. 장치 등록]  [2. 장치 선택]  [3. 종 료]\n:")

        if a == '1':
            t_create_dev_info()

        elif a == '2':
            connect_dev()
            
        elif a == '3':
            break

        else:
            print("올바른 번호를 입력하세요.")
            
main()
