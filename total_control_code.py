import os
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

# 장비 선택부
def create_dev_info() :
    
    data = ""
    dev_type = {
        '1':"R",
        '2':"SWI",
        '3':"ROC",
#        '4':"UBT",
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
#        "UBT":ubt_menu,
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

def roc_menu(device_info) :
    cli = connect_linux(device_info)

    if cli is None:
        print("리눅스 연결 실패로 메뉴를 종료합니다.")
        return
    
    while True :
        cmd = roc_cmd_select()

        if cmd is None:
            continue

        if cmd == "exit" :
            print("exit")
            break

        run_linux_cmd(cli, cmd)


    cli.close()


def roc_cmd_select() :
    
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
        0: 0
    }
    
    cmd = int(input(""" 
    실행할 작업의 번호 선택하세요.
    1. 방화벽 해제
    2. 패키지 업데이트
    3. 패키지 세팅(wget, vim, libstdc++, tar, gzip)
    4. 미니콘다 설치
    5. 주피터 노트북 실행 설정
    6. systempython, 파라미코 설치
    0. 종료
    선택: """))

    if cmd not in cmd_dict:
        print("잘못된 선택입니다.")
        return None

    if cmd == 0:
        print("프로그램을 종료합니다.")
        return "exit"
    
    return cmd_dict[cmd]


def run_linux_cmd(cli, cmd):
    
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
