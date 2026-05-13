import os
import sys
import time
import paramiko
from netmiko import ConnectHandler

# 테스트때문에 콘다 설치경로 바꿨음

# 절대경로
path = "./setting"
dev_path = path+"/devinfo"
backup_path = path + "/backup"
ip_path = path + "/ip"
route_path = path + "/route"


# 1. 계정 파일을 하나로 통합
# 2. 한 줄마다 한 계정씩 정보 입력, 데이터는 공백으로 분할
# 3. 계정 출력 : 쉽지.
# 4. 계정 선택 : readline 해서 라인 매칭 -> 딕셔너리 변환  
# 5. 

#def t_create_dev_info() :
#    type = input("장치의 종류를 선택하세요. [1.네트워크 장비] [2.스위치]")
    # 1. 장비 분류 선택 -> 파일 나누기
    # 2. 


# 장비 선택부
def create_dev_info() :
    
    data = ""
    dev_type = {
        '1':"R",
        '2':"SWI",
        '3':"ROC",
        '4':"UBT",
#        '5':"WIN"
    } 

    type=input("계정정보생성 장치 종류 선택:\n[ 1.라우터 ]\n[ 2.스위치 ]\n[ 3.록키  ]\n[ 4.우분투 ]\n")
    
    if not type in ['1','2','3','4'] :
        print("잘못된 입력입니다. 장치 타입에 해당하는 숫자로 선택해 주세요.")
        return       
    
    #장비 이름 입력시 ?,~#^&*$와 같은 문자 입력 못하게 막는 필터 추가하기.
    name=input("장치를 구분할 이름을 설정해주세요.")   
    host_ip = input("생성할 장비의 IP 주소를 입력하세요: ")
    username = input("생성할 장비의 계정 이름을 입력하세요: ")
    password = input("생성할 장비의 비밀번호를 입력하세요: ")
      
    if type == '1' or type == '2' :

        data = (
            "type=%s\n"
            "name=%s\n"
            "device_type=cisco_ios\n"
            "host=%s\n"
            "username=%s\n"
            "password=%s\n"
            "port=22\n"
            "conn_timeout=30\n"
            "auth_timeout=30\n"
            "banner_timeout=30\n"
            % (
                dev_type[type],
                name,
                host_ip,
                username,
                password,
            )
        )
    
    elif type == '3' or type == '4':
        
        data = (
            "type=%s\n"
            "name=%s\n"
            "host=%s\n"
            "username=%s\n"
            "password=%s\n"
            "port=22\n"
            % (
                dev_type[type],
                name,
                host_ip,
                username,
                password,
            )
        )

    os.makedirs(dev_path, exist_ok=True)    
    with open("%s/%s_%s.txt"%(dev_path,dev_type[type],name), 'w', encoding='utf-8') as devinfo : 
        devinfo.write(data)
    
    print("계정정보 생성이 완료되었습니다.\n%s/%s_%s.txt"%(dev_path,dev_type[type],name))

# 접속계정 파일 선택-----------------------------------------------


def select_dev() :
    device_list = os.listdir(dev_path)
    for i in range(len(device_list)) :
        device_list[i] = device_list[i].replace(".txt","")

    print("접속할 계정을 선택해 주세요.")
    print(device_list)
    file_name = input(":")
    
    if not file_name in device_list :
        print("%s? 존재하지 않는 계정입니다. 계정을 등록하고 사용해 주세요."%(file_name))
        return
        
    with open("%s/%s.txt"%(dev_path,file_name),"r",encoding="utf-8") as data :
        dev_info = dict()
        datas = data.readlines()    
        for i in datas :
            key, value = i.strip().split("=")
            dev_info[key] = value
    
    print(dev_info)
    return dev_info


def connect_dev() :
    dev_info = select_dev()

    if not dev_info:
        return

    dev_menu = {
        "R":cisco_menu,
        "SWI":cisco_menu,
        "ROC":roc_menu,
        "UBT":ubt_menu,
    }    

    func = dev_menu.get(dev_info["type"])

    if func :
        func(dev_info)
    else :
        print("지원하지 않는 장비 타입입니다.")
        return

# 리눅스 연결 부분-----------------------------------------------

def connect_linux(device_info) :
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print("리눅스 서버에 연결 중...")

    cli.connect(
        hostname=device_info["host"],
        port=22,
        username=device_info["username"],
        password=device_info["password"],
        timeout=20
    )

    return cli

# 록키 리눅스 처리 부분

def roc_ip_set(cli):
    ens = input("설정할 인터페이스를 입력하세요.(ex:ens160):")
    restart = "nmcli connection down"+ " "+ ens + " " + ";" + "nmcli connection up" + " "+ ens
    ipsetting = input("설정할 아이피 주소를 입력하세요:")           #변경할 ip정보 입력
    fixsetting = input("설정할 프리픽스를 입력하세요(예:/16):")     #변경할 프리픽스 입력
    stdin, stdout, stderr = cli.exec_command("nmcli connection modify " + ens + " ipv4.addresses " + ipsetting + fixsetting)
    print("ip가 변경됩니다... 프로그램이 종료됩니다.")
    stdin, stdout, stderr = cli.exec_command(restart) #위에서 설정한 재부팅 명령어 실행 
    sys.exit()  


def roc_gate_set(cli):                                                # 2번을 선택했을시에 gw 정보 변경
    ens = input("설정할 인터페이스를 입력하세요.(ex:ens160):")
    restart = "nmcli connection down"+ " "+ ens + " " + ";" + "nmcli connection up" + " "+ ens
    gatesetting = input("설정할 게이트웨이 주소를 입력하세요:")              #변경할 gw정보 입력
    stdin, stdout, stderr = cli.exec_command("nmcli connection modify"+" "+ ens +" "+ "ipv4.gateway"+" "+ gatesetting) #변경명령어
    print("ip가 변경됩니다... 프로그램이 종료됩니다.")
    stdin, stdout, stderr = cli.exec_command(restart) #위에서 설정한 재부팅 명령어 실행 
    sys.exit()  
        


def roc_menu(device_info) :
    cli = connect_linux(device_info)
    if cli is None:
        print("리눅스 연결 실패로 메뉴를 종료합니다.")
        return
    
    while True :
        cmd = roc_cmd_select()

        if cmd is None:
            continue

        if cmd == 0 :
            print("exit")
            break

        run_linux_cmd(cli, cmd)


    cli.close()


def roc_cmd_select() :
    
    cmd = int(input(""" 
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

    if cmd not in range(0,9):
        print("잘못된 선택입니다.")
        return None

    if cmd == 0:
        print("프로그램을 종료합니다.")
        return 0
    
    return cmd


def run_linux_cmd(cli, cmd):
    
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
    
    if cmd in range(1,7):
        cmds = cmd_dict[cmd]
        for i in cmds:
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
        func = cmd_dict[cmd]
        if func :
            func(cli)
        else :
            print("함수 실행이 안되는데요??")
          
# cisco 장비 처리 부분


# cisco 장비 공통 처리 부분-----------------------------------------------


def connect_cisco(device_info):
    conn_info = device_info.copy()
    conn_info.pop("type", None)
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
    
    with open("%s/%s_%s_backup.txt" %(backup_path,device_info["type"],device_info["name"]), "w") as file:
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


# cisco 메뉴 처리 부분-----------------------------------------------


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

# ------------------------------------------------------------

#ubuntu로 수정

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


#ip 정보 백업(파일생성)

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

# 넷플랜 파일명 가져오기 - >리스트로    
def ubt_netplan_list_meth(output):
    file = open("netplan_ls", "w", encoding = "utf-8")
    file.write(output)
    file.close()

    file = open("netplan_ls", "r", encoding = "utf-8")
    global yaml
    yaml = file.read().split()
    file.close()

# yaml 파일명 보여주고 어떤 파일 보여줄 지 .
def ubt_yaml_cat():
    for i in range(len(yaml)):
        print("%d. %s"%(i+1,yaml[i]))
    global y_num
    y_num = int(input("파일을 선택해주세요 : "))
    yaml_cat = "cat /etc/netplan/".join(yaml[y_num-1])

# yaml 안에 있는 내용을 netplan 장비명, 한줄 띄고 아웃풋 입력 -> 네트워크 장치 정보 입력
def ubt_make_yaml_cat(output):
    file = open("netplan_cat", "w", encoding = "utf-8")
    data = yaml[y_num] +"\n"+ output
    file.write(data)
    file.close()


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

#패키지 확인, 설치
def ubt_package_check_install(cli):
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

def ubt_run_cmd(cli, shell, cmd):

    firewall_meth = [
        "systemctl disable --now ufw",
        "systemctl status ufw",
        # Ubuntu는 보통 SELinux가 없으므로 아래 두 줄은 필요 시에만 사용 (없으면 에러 발생 가능)
        #"if [ -f /etc/selinux/config ]; then sed -i 's/^SELINUX=enforcing/SELINUX=disabled/' /etc/selinux/config; fi",
        #"command -v setenforce >/dev/null && setenforce 0 || echo 'SELinux not found'",
        "init 6"
    ]

    package_update_meth = ["apt-get update && apt-get -y upgrade"]

    package_setting_meth = [
        "apt-get update",
        "apt-get -y install software-properties-common wget vim libstdc++6 tar gzip build-essential",
        # Ubuntu는 crb 설정이 필요 없으므로 생략하고 기본 패키지 업데이트만 진행
        "apt-get -y update && apt-get -y upgrade"
    ]

    #miniconda_meth = [
    #    "wget https://www.ubiedu.co.kr/Miniconda3-latest-Linux-x86_64.sh",

    miniconda_meth = [
        "wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh", # 학원 사이트 대신 공식 url 사용.
        "chmod u+x Miniconda3-latest-Linux-x86_64.sh",
        "./Miniconda3-latest-Linux-x86_64.sh -b -p /root/miniconda3", 
        "sed -i '$a export PATH=$PATH:/root/miniconda3/bin' /etc/bash.bashrc", # Ubuntu 전역 경로
        "/root/miniconda3/bin/conda config --set auto_activate false", 
        "/root/miniconda3/bin/conda config --add channels defaults",
        "/root/miniconda3/bin/conda install jupyter -y"
    ]

    jupyternotebook_meth = [
        "apt-get install -y expect",
        
        # password 설정 부분을 더 범용적인 명령어로 교체
        "expect -c 'spawn /root/miniconda3/bin/jupyter notebook password; expect \"Enter password:\"; send \"asd123!@\\r\"; expect \"Verify password:\"; send \"asd123!@\\r\"; expect eof'",
        
        # 스크립트 생성 시 하이픈(-) 대신 python -m jupyter 사용
        "echo \"#!/bin/bash\" > /root/jupyter_start.sh",
        "echo \"/root/miniconda3/bin/python3 -m jupyter notebook --allow-root --ip=0.0.0.0 --port=8080 --no-browser &\" >> /root/jupyter_start.sh",
        "chmod +x /root/jupyter_start.sh",
        
        "./jupyter_start.sh" # 설정 후 바로 실행까지 추가
    ]

    pythonsystem_paramico_meth = [
        "/root/miniconda3/bin/conda install pip -y",
        "/root/miniconda3/bin/pip install --upgrade pip",
        "/root/miniconda3/bin/pip install paramiko", 
        "/root/miniconda3/bin/conda install -y -c conda-forge types-cryptography",
        "/root/miniconda3/bin/python3 -m pip install ipykernel",
        "/root/miniconda3/bin/python3 -m ipykernel install --user --name system-python --display-name \"Python 3 (System)\""
    ]
    
    #넷플랜에 대해서 yaml 파일의 이름 활용하기 위한 파일 생성 함수
    netplan_ls = ["ls /etc/netplan"]

    #yaml cat 명령어 생성기
    yaml_cat = ""

    #리눅스 ip 정보
    ub_ip_a = ["ip a"]

    ub_ip_r = ["ip r"]

    cmd_dict = {
            1: firewall_meth,
            2: package_update_meth,
            3: package_setting_meth,
            4: miniconda_meth,
            5: jupyternotebook_meth,
            6: pythonsystem_paramico_meth,
            9: netplan_ls,
            10: 10,
            11: ub_ip_a,
            12: ub_ip_r,
            13: 13,
        }

    if cmd in [7, 8]:
        # 1. 인터페이스 이름 가져오기 (lo 제외 첫번째 장치 / ens33 같은 것)
        shell.send("ip -o link show | awk -F': ' '{print $2}' | grep -v 'lo' | head -n1\n")
        time.sleep(1)
        interface = shell.recv(1024).decode().split('\n')[1].strip()
        
        # 2. 파일 리스트 확인 (없을 경우 대비)
        shell.send("ls /etc/netplan/\n")
        time.sleep(1)
        files = shell.recv(1024).decode().split()
        target_file = [f for f in files if f.endswith('.yaml')][0]
        
        if cmd == 7:
            new_yaml = ubt_create_dhcp_yaml(interface)
            print("%s 네트워크를 DHCP로 전환합니다."%interface)
        else:
            new_yaml = ubt_create_static_yaml(interface)
            print("%s 네트워크를 정적 IP로 전환합니다."%interface)

        # 3. 파일 쓰기 및 적용 (cat <<EOF 사용)
        setup_cmd = f"cat <<EOF > /etc/netplan/{target_file}\n{new_yaml}EOF\n"
        shell.send(setup_cmd)
        time.sleep(1)
        shell.send("netplan apply\n")
        time.sleep(2)
        print("netplan apply가 실행되었습니다.")
        return
    
    if (cmd == 13):
        ubt_package_check_install(cli)
        return

    for i in cmd_dict[cmd]:
        print("-> 실행 중: %s" % i)
        if(i == 10):
            ubt_yaml_cat()
        # 명령어 전송 (끝에 \n 필수)
        shell.send(i + "\n")
        time.sleep(1) # 명령어 처리 대기 (패키지 설치 시 더 길게 조절 필요)
        
        # 결과 수신
        if shell.recv_ready():
            output = shell.recv(65535).decode('utf-8')
            print("[결과]\n%s" % output)
            if(i == 10):
                ubt_make_yaml_cat(output)

        if i == "init 6":
            print("시스템을 재부팅합니다. 연결이 끊어집니다.")
            break
   
    if (cmd == 9) : 
        ubt_netplan_list_meth(output)

    if (cmd == 11) :
        ubt_ip_a(output)
    if (cmd == 12) :
        ubt_ip_r(output)
    
    if (cmd == 13):
        ubt_package_check_install(cli)

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
# 메인 실행 부분-----------------------------------------------


def main() :
    
    while True :
        select = input("[시작 메뉴]\n1.계정 생성\n2.장비 접속\n0.프로그램 종료\n 원하는 기능을 선택하세요 : ")
        if not select in ['1','2','0'] :
            print("잘못된 입력입니다.")
            continue
        elif select == '0' :
            print("프로그램을 종료합니다.")
            break
        elif select == '1' :
            create_dev_info()
        elif select == '2' :
            connect_dev()

main()
