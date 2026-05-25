#### import os
import sys
import time
import paramiko
from netmiko import ConnectHandler

# 절대경로 -> 상대경로로 바꾸기 어떰?
# 절대경로
path = "./setting"
dev_path = path + "/devinfo"
backup_path = path + "/backup"
ip_path = path + "/ip"
route_path = path + "/route"
dhcp_path = path + "/dhcp"
html_index_path = path + "/index"

def roc_firewall_disable(cli) :
    cmd = """cat << 'EOF' > /root/firewall_disable.sh
#!/bin/bash
systemctl disable --now firewalld
systemctl stop firewalld
setenforce 0
sed -i 's/^SELINUX=.*/SELINUX=disabled/' /etc/selinux/config
echo "init6 로 리부트 해야 firewalld 해제 적용됩니다"
EOF
chmod +x /root/firewall_disable.sh &&
/root/firewall_disable.sh
"""
    stdin, stdout, stderr = cli.exec_command(cmd)
    output, error = cli_error_check(stdout, stderr)
    if not error :
        print("방화벽 해제 커맨드 생성 완료.")
    
def roc_httpd_set(cli):

    print("\n[1/3] httpd 설치 및 서비스 활성화 중...")

    cmd = '''
dnf -y install httpd &&
systemctl enable --now httpd
'''
    stdin, stdout, stderr = cli.exec_command(cmd)
    cli_error_check(stdout, stderr)

    print("httpd 설치 및 서비스 활성화 완료")

    print("\n[2/3] httpd 설정 정보 입력")

    admin_email = "root@localhost"
    server_name = input("서버 이름 입력(ex: localhost:80 또는 IP:포트) : ")
    document_root = input("루트 디렉터리 경로 입력(ex: /home/test) : ")
    directory_permission = input("디렉터리 권한 입력(ex: 755 권장) : ")

    print("\n[2/3] httpd 설정 파일 수정 및 권한 설정 중...")

    cmd = '''
mkdir -p %s &&
sed -i 's|^ServerAdmin .*|ServerAdmin %s|g' /etc/httpd/conf/httpd.conf &&
sed -i 's|^#\\?ServerName .*|ServerName %s|g' /etc/httpd/conf/httpd.conf &&
sed -i 's|^DocumentRoot .*|DocumentRoot "%s"|g' /etc/httpd/conf/httpd.conf &&
( grep -q '<Directory "%s">' /etc/httpd/conf/httpd.conf || sed -i '/<IfModule mime_module>/i\\
<Directory "%s">\\
    AllowOverride None\\
    Options None\\
    Require all granted\\
</Directory>\\
' /etc/httpd/conf/httpd.conf ) &&
chmod -R %s %s
''' % (
        document_root,
        admin_email,
        server_name,
        document_root,
        document_root,
        document_root,
        directory_permission,
        document_root
    )

    stdin, stdout, stderr = cli.exec_command(cmd)
    cli_error_check(stdout, stderr)

    print("httpd 설정 파일 수정 완료")

    print("\n[3/3] index.html 생성 중...")

    html_content = "<h1>Welcome to %s!</h1>" % (server_name)
    target_index_path = "%s/index.html" % (document_root)

    cmd = """tee %s > /dev/null << 'EOF'
%s
EOF
chmod 644 %s
""" % (
        target_index_path,
        html_content,
        target_index_path
    )

    stdin, stdout, stderr = cli.exec_command(cmd)
    cli_error_check(stdout, stderr)

    if "/home/" in document_root:

        owner_user = document_root.split("/")[2]

        cmd = "chown %s:%s %s" % (
            owner_user,
            owner_user,
            target_index_path
        )

        stdin, stdout, stderr = cli.exec_command(cmd)
        cli_error_check(stdout, stderr)

        print("index.html 소유권을 %s 계정으로 변경 완료" % (owner_user))

    stdin, stdout, stderr = cli.exec_command("httpd -t")
    httpd_check, error = cli_error_check(stdout, stderr)
    
    check_result = httpd_check + error
    
    print("httpd 설정 검사 결과:\n%s" % (check_result))
    
    if "Syntax OK" not in check_result:
        print("httpd 설정 오류 발생. 서비스를 재시작하지 않습니다.")
        return
    
    stdin, stdout, stderr = cli.exec_command("systemctl restart httpd")
    cli_error_check(stdout, stderr)

    print("httpd 서버 재시작 완료")
    print("Rocky httpd 설정 완료")

    
def roc_index_backup(cli) :

    os.makedirs(html_index_path, exist_ok=True)
    cmd = "cat /etc/httpd/conf/httpd.conf | grep ^DocumentRoot"
    stdin, stdout, stderr = cli.exec_command(cmd)
    tmp = stdout.read().decode('utf-8').strip().split()
    doc_root = tmp[1].strip("\"")
    cmd = "cat %s/index.html"%(doc_root)
    stdin, stdout, stderr = cli.exec_command(cmd)
    output = stdout.read().decode('utf-8').strip()
    
    filename = input("저장할 파일의 이름을 입력하세요:")
    path2 = html_index_path + '/' + filename + '.txt'
    file_new = open(path2,"w",encoding = "utf-8")
    file_new.write(output)
    print("파일백업이 완료되었습니다.")

#def roc_index_upload(cli) :
#
#    backup_list = os.listdir(html_index_path)
#    for i in range(len(backup_list)):
#        backup_list[i] = backup_list[i].replace(".txt", "")
    
#    print(backup_list)
#    name = input("업로드할 인덱스 파일명을 입력하세요. : ")

    # name 파일 열기 -> read 로 통짜 문자열로 불러와서 변수 index_html 에 저장 -> 이 값을 업로드하는 cmd 명령어 작성 
    
#    cmd = "실행할 명령어 생성. 문자열로. "
#    stdin, stdout, stderr = cli.exec_command(cmd)


    
#    if stderr :
#        print("명령어 실행 오류 발생.")
#        print(stderr)
#    else :
#        print(stdout)
    


def cli_error_check(stdout, stderr):

    output = stdout.read().decode("utf-8").strip()
    error = stderr.read().decode("utf-8").strip()

    if output:
        print(output)

    if error:
        print("[알림/에러]", error)

    return output, error


def ubt_httpd_set(cli):
    
    # --- 1. 방화벽 비활성화 및 SELinux 도구 설치 ---
    print("\n[1/6] 방화벽 설정 및 SELinux 도구 설치 중...")

    firewall_commands = '''
systemctl disable --now ufw &&
systemctl stop ufw &&
apt -y install selinux-utils &&
(command -v setenforce >/dev/null && setenforce 0 || echo "setenforce 없음")
'''

    stdin, stdout, stderr = cli.exec_command(firewall_commands)
    cli_error_check(stdout, stderr)
    print("방화벽 설정 및 selinux 설치 실행 완료")


    # --- 2. 유저 생성 (manager) & 대화형 비밀번호 설정 ---
    print("[입력] 새로 생성할 'manager' 계정의 비밀번호를 정해주세요.")
    manager_password = input("manager password : ")

    if manager_password.strip() == "":
        print("비밀번호가 입력되지 않았습니다. 스크립트를 종료합니다.")
        return

    print("\n[2/6] manager 유저 생성 및 비밀번호 설정 중...")
    cmd = 'id manager >/dev/null 2>&1 || useradd -m manager; echo "manager:%s" | chpasswd' % (manager_password)
    stdin, stdout, stderr = cli.exec_command(cmd)
    cli_error_check(stdout, stderr)
    print("manager 유저 생성, 비밀번호 등록 완료")

    # --- 3. apt 업데이트 및 업그레이드 ---
    print("\n[3/6] apt 패키지 업데이트 및 업그레이드 중... (시간이 다소 소요될 수 있습니다)")
    cmd = "DEBIAN_FRONTEND=noninteractive apt -y update && DEBIAN_FRONTEND=noninteractive apt -y upgrade"
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=300)
    cli_error_check(stdout, stderr)
    print("apt 업데이트 완료")

    # --- 4. nginx 설치 ---
    print("\n[4/6] Nginx 설치 중...")
    stdin, stdout, stderr = cli.exec_command('DEBIAN_FRONTEND=noninteractive apt -y install nginx', timeout=150)
    cli_error_check(stdout, stderr)
    print("Nginx 설치 완료")

    # --- 5. config 경로 새로운 유저 홈으로 변경 & 권한 수정 ---
    print("\n[5/6] Nginx 설정 파일 수정 및 디렉토리 권한 설정 중...")
    cmd = '''
mkdir -p /home/manager/log &&
usermod -aG manager www-data &&
chown -R manager:manager /home/manager &&
chmod 750 /home/manager &&
chmod -R 755 /home/manager/log
'''
    stdin, stdout, stderr = cli.exec_command(cmd)
    cli_error_check(stdout, stderr)
    # nginx 의 설정 생성
    cmd = """cat << 'EOF' > /etc/nginx/sites-enabled/default
server {
    listen 80;
    server_name localhost;

    location / {
        root /home/manager;
        index index.html;
    }

    access_log /home/manager/log/access.log;
    error_log /home/manager/log/manager_error.log;
}
EOF
"""
    print("-> Nginx 설정 파일 주입 중...")
    stdin, stdout, stderr = cli.exec_command(cmd)
    cli_error_check(stdout, stderr)
    print("Nginx 설정 파일(/etc/nginx/sites-enabled/default) 변경 완료")

    # --- 6. index 파일 생성 ---
    print("\n[6/6] index.html 파일 생성 및 Nginx 재시작 중...")

    cmd = '''
touch /home/manager/index.html &&
echo "<h1>Welcome to Manager Home</h1>" > /home/manager/index.html &&
chown manager:manager /home/manager/index.html &&
chmod 644 /home/manager/index.html
'''

    stdin, stdout, stderr = cli.exec_command(cmd)
    cli_error_check(stdout, stderr)

    stdin, stdout, stderr = cli.exec_command('nginx -t')
    nginx_check, error = cli_error_check(stdout, stderr)

    print("Nginx Test 결과:\n%s" % (nginx_check))

    stdin, stdout, stderr = cli.exec_command('systemctl restart nginx')
    cli_error_check(stdout, stderr)

    print("Nginx 서버 재시작 완료")

    # --- 최종 안내 및 리부트 ---
    print("\n--- 모든 작업이 완료되었습니다! ---")
    print("서버가 재부팅되면 SSH 연결이 끊어집니다.")
    
    stdin, stdout, stderr = cli.exec_command('reboot')
    cli.close()
    print("SSH 연결 종료 및 서버 재부팅 프로세스 시작.")



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
    os.makedirs(dev_path, exist_ok=True)
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

def roc_package_update(cli):
    
    cmd = [
        "dnf -y update && dnf -y upgrade"
    ]

    roc_run_command(cli,cmd)

def roc_package_setting(cli):

    cmd = [
    "dnf -y install epel-release wget vim libstdc++ tar gzip expect",
    "dnf makecache",
    "dnf config-manager --set-enabled crb",
    "dnf -y update && dnf -y upgrade"
    ]

    roc_run_command(cli,cmd)

def roc_miniconda_install(cli):
    cmd = [
        "wget -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh",
        "chmod u+x Miniconda3-latest-Linux-x86_64.sh",
        "./Miniconda3-latest-Linux-x86_64.sh -b",
        "sed -i '$a export PATH=$PATH:/root/miniconda3/bin' /etc/bashrc",
        "/root/miniconda3/bin/conda config --set auto_activate false",
        "/root/miniconda3/bin/conda tos accept --override-channels --channel \"https://repo.anaconda.com/pkgs/main\"",
        "/root/miniconda3/bin/conda tos accept --override-channels --channel \"https://repo.anaconda.com/pkgs/r\"",
        "/root/miniconda3/bin/conda install jupyter -y"
    ]

    roc_run_command(cli,cmd)

def roc_jupyter_setting(cli):

    cmd = [
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
    roc_run_command(cli,cmd)


def roc_py_package_install(cli):

    cmd = [
        "/root/miniconda3/bin/conda install pip -y",
        "/root/miniconda3/bin/pip install --upgrade pip",
        "/root/miniconda3/bin/pip install paramiko",
        "/root/miniconda3/bin/conda install -y -c conda-forge types-cryptography",
        "/root/miniconda3/bin/python3 -m pip install ipykernel",
        "/root/miniconda3/bin/python3 -m ipykernel install --user --name system-python --display-name \"Python 3 (System)\"",
        "/root/miniconda3/bin/pip install netmiko"
    ]
    roc_run_command(cli,cmd)

def roc_run_command(cli,cmd) :
    for i in cmd:
        print("-> 실행 중: %s" % i)
        if i == "init 6":
            print("시스템을 재부팅합니다. 연결이 끊어집니다.")
            cli.exec_command(i)
            time.sleep(2)
            sys.exit(0)
        stdin, stdout, stderr = cli.exec_command(i)

        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        if error:
            print("[알림/에러] %s" % error)

        if output:
            print("[결과] %s" % output)
    
def roc_menu(device_info) :

    cmd_dict = {
            1: roc_package_update,
            2: roc_package_setting,
            3: roc_miniconda_install,
            4: roc_py_package_install,
            5: roc_jupyter_setting,
            6: roc_ip_set,
            7: roc_gate_set,
            8: roc_httpd_set,
            9: roc_index_backup,
            10: roc_firewall_disable,
#           11: roc_index_upload,      
            0: 0
    } 

    cli = connect_linux(device_info)
    if cli is None:
        print("리눅스 연결 실패로 메뉴를 종료합니다.")
        return
    while True :

        select = int(input(""" 
        실행할 작업의 번호를 선택하세요.
        1. 패키지 업데이트
        2. 패키지 세팅
        3. 미니콘다 설치
        4. 시스템파이썬, 파라미코 설치
        5. 주피터 노트북 실행 설정
        6. 록키 ip 설정
        7. 록키 게이트웨이 설정
        8. httpd 아파치 웹 서비스 설치 및 설정
        9. index.html 백업
        10. 방화벽 해제 스크립트 disable_firewall.sh 설치
        #11. index.html 적용(미완성)
        0. 종료
        선택: """))
   
        if select not in cmd_dict:
            print("없는 번호입니다. 다시 입력해 주세요.")
            continue

        if select == 0 :
            print("exit")
            break
        else :
            func = cmd_dict[select]
            if func :
                func(cli)

    cli.close()

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

    cmd = "show vtp status"
    output = cli.send_command(cmd)
    
    with open("%s/%s_%s_backup_vtp.txt" %(backup_path,device_info["type"],device_info["name"]), "w") as file:
        file.write(output)

    cmd = "show int trunk"
    output = cli.send_command(cmd)
    
    with open("%s/%s_%s_backup_trunk.txt" %(backup_path,device_info["type"],device_info["name"]), "w") as file:
        file.write(output)

    cmd = "show vlan-switch bri"
    output = cli.send_command(cmd)
    
    with open("%s/%s_%s_backup_vlan.txt" %(backup_path,device_info["type"],device_info["name"]), "w") as file:
        file.write(output)

    cmd = "show spanning-tree bri"
    output = cli.send_command(cmd)
    
    with open("%s/%s_%s_backup_stp.txt" %(backup_path,device_info["type"],device_info["name"]), "w") as file:
        file.write(output)
        
    print("백업 완료")

def cisco_backup_vtp(cli,device_info):
    
    os.makedirs(backup_path, exist_ok=True)
    
    cmd = "show vtp status"
    output = cli.send_command(cmd)
    
    with open("%s/%s_%s_backup_vtp.txt" %(backup_path,device_info["type"],device_info["name"]), "w") as file:
        file.write(output)
        
    print("vtp status 백업 완료")
    
def cisco_backup_trunk(cli,device_info):
    
    os.makedirs(backup_path, exist_ok=True)
    
    cmd = "show int trunk"
    output = cli.send_command(cmd)
    
    with open("%s/%s_%s_backup_trunk.txt" %(backup_path,device_info["type"],device_info["name"]), "w") as file:
        file.write(output)
        
    print("trunk interface 백업 완료")
    
def cisco_backup_vlan(cli,device_info):
    
    os.makedirs(backup_path, exist_ok=True)
    
    cmd = "show vlan-switch bri"
    output = cli.send_command(cmd)
    
    with open("%s/%s_%s_backup_vlan.txt" %(backup_path,device_info["type"],device_info["name"]), "w") as file:
        file.write(output)
        
    print("vlan port brief 백업 완료")

def cisco_backup_stp(cli,device_info):
    
    os.makedirs(backup_path, exist_ok=True)
    
    cmd = "show spanning-tree bri"
    output = cli.send_command(cmd)
    
    with open("%s/%s_%s_backup_stp.txt" %(backup_path,device_info["type"],device_info["name"]), "w") as file:
        file.write(output)
        
    print("spanning tree brief 백업 완료")

# vtp 설정부
from time import sleep

# vtp 설정부
def vtp_setting(cli):
    mode_menu = {
        1: "server",
        2: "transparent",
        3: "client"
    }

    while True:
        user_input = input("""vtp 설정 메뉴를 선택해주세요:
1. domain 설정
2. password 설정
3. 모드 설정(Ser, Trans, Cli)

0. 종료
""")
        # 공백 입력 예외 처리 및 숫자 변환
        if not user_input.strip():
            continue
        mode = int(user_input)

        if mode == 0:
            print("VTP 설정을 종료합니다.")
            break

        elif mode == 1:
            domain = input("사용하실 vtp 도메인 ID를 입력해주세요: ")
            
            commands = [
                "vlan database",
                f"vtp domain {domain}",
                "exit"
            ]
            cli.send_config_set(commands)

        elif mode == 2:
            password = input("사용하실 vtp 비밀번호를 입력해주세요: ")
            
            commands = [
                "vlan database",
                f"vtp password {password}",
                "exit"
            ]
            cli.send_config_set(commands)

        elif mode == 3:
            mode_select_input = input("""모드를 선택해주세요 : 
1. Server mode
2. Transparent mode
3. Client mode
""")
            if not mode_select_input.strip():
                continue
            mode_select = int(mode_select_input)
            
            # 선택한 번호가 1, 2, 3 중에 있는지 확인 (KeyError 방지)
            if mode_select in mode_menu:
                vtp_mode = mode_menu[mode_select]
                
                commands = [
                    "vlan database",
                    f"vtp {vtp_mode}",
                    "exit"
                ]
                output = cli.send_config_set(commands)
                print(output)
            else:
                print("잘못된 모드 번호입니다. 다시 시도해주세요.")


# trunk 설정부
def trunk_setting(cli) :
    while True :
        flag = input("트렁크 경로를 추가로 입력하시겠습니까? (Y / N) : ").strip().upper()
        if flag == "N":
            break
        
        trunk_int = input("트렁크로 설정할 인터페이스를 입력해주세요 (ex: f0/1): ").strip()
        cmd = [
            f"interface {trunk_int}",
            "switchport mode trunk",
            "switchport trunk allowed vlan all"
        ]
        cli.send_config_set(cmd)
        print(f"{trunk_int} 인터페이스 트렁크 설정 완료!")
        sleep(1)

#vlan 생성 및 삭제
def vlan_edit(cli) :
    while True:
        # input() 결과를 int()로 감싸서 숫자로 변환합니다.
        user_input = input("""1. vlan 추가
2. vlan 삭제

0. 종료
""")
        
        # 공백 입력 예외 처리 및 숫자 변환
        if not user_input.strip():
            continue
        mode = int(user_input)
    
        if mode == 0:
            print("프로그램을 종료합니다.")
            break
    
        elif mode == 1:
            vlan = input("추가할 vlan 번호를 넣어주세요 (ex : 10): ")
            commands = [
                "vlan database",
                f"vlan {vlan}",
                "exit"
            ]
            cli.send_config_set(commands)
    
        elif mode == 2:
            vlan = input("삭제할 vlan 번호를 넣어주세요 (ex : 10): ")
            commands = [
                "vlan database",
                f"no vlan {vlan}",
                "exit"
            ]
            output = cli.send_config_set(commands)

#vlan 포트 지정
def vlan_access(cli) :
    port_int = input("포트 인터페이스를 입력해주세요 : ").strip()
    vlan = input("몇 번 vlan으로 설정하시겠습니까? : (ex : 10) ").strip()
    
    # send_config_set은 자동으로 conf t를 해주므로 conf t와 end는 빼는 것이 안전합니다.
    commands = [
        f"interface {port_int}",
        "switchport mode access",
        f"switchport access vlan {vlan}" 
    ]
    output = cli.send_config_set(commands)
    print(output)

#stp 설정 (priority값)
def stp_setting(cli) :
    vlan = input("몇 번 vlan으로 설정하시겠습니까? : (ex : 10) ").strip()
    prio = input("priority값을 입력해주세요 : (ex : 4096) ").strip()
    commands = [
        f"spanning-tree vlan {vlan} priority {prio}"
    ]
    output = cli.send_config_set(commands)
    print(output)

#라우터 inter vlan 포트 설정
def inter_vlan(cli) :
    gate_port = input("게이트웨이 포트를 입력해주세요 : (ex : f0/0) ").strip()

    # 물리 포트 서브인터페이스 생성 전 no shut 활성화
    init_commands = [
        f"interface {gate_port}",
        "no shutdown"
    ]
    cli.send_config_set(init_commands)

    while True:
        flag = input("inter vlan을 설정하시겠습니까? : (Y / N) ").strip().upper()
        if flag == "Y": # 대문자 통일
            vlan_domain = input("vlan 번호(도메인)를 입력하세요 : (ex : f0/0.10 이면 10만 입력): ").strip()
            vlan_gate = input("vlan의 gateway IP를 입력해주세요 : ").strip()
            vlan_mask = input("vlan의 subnet mask를 입력해주세요 : ").strip()
            
            # 매번 독립적으로 실행되도록 구성하여 프롬프트 꼬임 방지
            commands = [
                f"interface {gate_port}.{vlan_domain}",
                f"encapsulation dot1Q {vlan_domain}",
                f"ip address {vlan_gate} {vlan_mask}"
            ]
            output = cli.send_config_set(commands)
            print(output)
        else:
            break


def cisco_restore(cli):

    backup_list = os.listdir(backup_path)
    for i in range(len(backup_list)):
        backup_list[i] = backup_list[i].replace(".txt", "")

    print(backup_list)
    name = input("복구할 백업 파일명을 입력하세요. : ")

    file = open("%s/%s.txt" % (backup_path, name), "r", encoding="utf-8")
    lines = file.readlines()
    file.close()

    interface_cmd = []
    route_cmd = []

    for i in range(len(lines)):
        clear_line = lines[i].strip()

        if clear_line == "" or clear_line == "!":
            continue

        # interface 블록 전체 추출
        if clear_line.startswith("interface"):
            interface_cmd.append(clear_line)

            cnt = 1
            while i + cnt < len(lines):
                next_line = lines[i + cnt].strip()

                if next_line == "!":
                    break

                if next_line == "":
                    cnt += 1
                    continue

                interface_cmd.append(next_line)
                cnt += 1

        # 라우팅/NAT/DHCP 등 글로벌 설정 구간 추출
        if clear_line.startswith("ip forward-protocol"):
            cnt = 1
            while i + cnt < len(lines):
                new_clear_line = lines[i + cnt].strip()

                if new_clear_line.startswith("no ip http server"):
                    break

                if new_clear_line == "" or new_clear_line == "!":
                    cnt += 1
                    continue

                route_cmd.append(new_clear_line)
                cnt += 1

    tot_cmd_lines = []
    tot_cmd_lines.extend(interface_cmd)
    tot_cmd_lines.extend(route_cmd)

    tot_cmd = "\n".join(tot_cmd_lines)

    print("복원할 명령어 목록")
    print(tot_cmd)

    command_cisco(cli, tot_cmd)

# NAT 설정을 백업 파일에서 추출하여 복원하는 함수
def nat_restore(cli):
    backup_list = os.listdir(backup_path)
    if not backup_list:
        print("백업 파일이 없습니다.")
        return

    for i in range(len(backup_list)):
        backup_list[i] = backup_list[i].replace(".txt", "")
    
    print(backup_list)
    name = input("NAT 설정을 복구할 백업 파일명을 입력하세요 : ")

    try:
        with open("%s/%s.txt" % (backup_path, name), "r", encoding="utf-8") as file:
            lines = file.readlines()
    except FileNotFoundError:
        print("파일을 찾을 수 없습니다.")
        return

    nat_commands = []
    
    # 백업 파일 내에서 NAT 관련 설정만 필터링
    for line in lines:
        clean_line = line.strip()
        # 글로벌 NAT 설정 추출 (static, pool, list 등)
        if clean_line.startswith("ip nat inside") or clean_line.startswith("ip nat pool") or clean_line.startswith("access-list"):
            nat_commands.append(clean_line)
        
        # 인터페이스 nat 설정은 복잡하므로, 전체 복원을 권장하거나 
        # 특정 인터페이스 키워드(int e0/0 등)와 그 다음줄의 nat inside/outside를 매칭해야 합니다.

    if not nat_commands:
        print("해당 백업 파일에 NAT 관련 설정이 존재하지 않습니다.")
        return

    print("--- 복구할 NAT 설정 리스트 ---")
    for cmd in nat_commands:
        print(cmd)
    
    confirm = input("위 설정을 적용하시겠습니까? (y/n): ")
    if confirm.lower() == 'y':
        command_cisco(cli, nat_commands)
        print("NAT 설정 복구 완료!")


def dhcp_restore(cli):

    backup_list = os.listdir(backup_path)
    for i in range(len(backup_list)):
        backup_list[i] = backup_list[i].replace(".txt", "")

    print(backup_list)
    name = input("DHCP 설정을 복구할 백업 파일명을 입력하세요 : ")

    file = open("%s/%s.txt" % (backup_path, name), "r", encoding="utf-8")
    lines = file.readlines()
    file.close()

    dhcp_cmd = []

    for i in range(len(lines)):
        clear_line = lines[i].strip()

        if clear_line == "" or clear_line == "!":
            continue

        # DHCP excluded-address 추출
        if clear_line.startswith("ip dhcp excluded-address"):
            dhcp_cmd.append(clear_line)

        # DHCP pool 블록 전체 추출
        if clear_line.startswith("ip dhcp pool"):
            dhcp_cmd.append(clear_line)

            cnt = 1
            while i + cnt < len(lines):
                next_line = lines[i + cnt].strip()

                if next_line == "!":
                    break

                if next_line == "":
                    cnt += 1
                    continue

                dhcp_cmd.append(next_line)
                cnt += 1

    if not dhcp_cmd:
        print("해당 백업 파일에 DHCP 설정이 없습니다.")
        return

    tot_cmd = "\n".join(dhcp_cmd)

    print("복원할 DHCP 명령어 목록")
    print(tot_cmd)

    apply = input("위 DHCP 설정을 적용하시겠습니까? (y/n): ")

    if apply.lower() == "y":
        command_cisco(cli, tot_cmd)
        print("DHCP 설정 복원 완료!")
    
    
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

    os.makedirs(dhcp_path, exist_ok=True)

    file_name = input("저장할 DHCP 설정 파일 이름: ")
    save_path = dhcp_path + "/" + file_name + ".txt"

    with open(save_path, "w", encoding="utf-8") as file:
        file.write(command)

    print("DHCP 설정이 저장되었습니다.")
    print("저장 위치:", save_path)

    apply = input("바로 적용하시겠습니까? (y/n): ")

    if apply.lower() == "y":
        command_cisco(cli, command)


def dhcp_apply(cli):

    os.makedirs(dhcp_path, exist_ok=True)

    dhcp_list = os.listdir(dhcp_path)

    if not dhcp_list:
        print("저장된 DHCP 설정 파일이 없습니다.")
        return

    for i in range(len(dhcp_list)):
        dhcp_list[i] = dhcp_list[i].replace(".txt", "")

    print(dhcp_list)

    name = input("적용할 DHCP 설정 파일명을 입력하세요 : ")

    if name not in dhcp_list:
        print("존재하지 않는 DHCP 설정 파일입니다.")
        return

    with open("%s/%s.txt" % (dhcp_path, name), "r", encoding="utf-8") as file:
        command = file.read()

    print("불러온 DHCP 설정\n")
    print(command)

    apply = input("위 설정을 적용하시겠습니까? (y/n): ")

    if apply.lower() == "y":
        command_cisco(cli, command)
        print("DHCP 설정 적용 완료!")


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
        # 백업 / 복원
        "1": cisco_backup,
        "2": cisco_restore,

        # IP 설정
        "3": ip_setting,
        "4": ip_preset,

        # Route 설정
        "5": route_setting,
        "6": route_preset,
        "7": static_router_setting,

        # NAT
        "8": nat_setting,
        "9": nat_restore,

        # DHCP
        "10": dhcp_setting,
        "11": dhcp_apply,
        "12": dhcp_restore,

        # SVI
        "13": svi_setting,

        #5_18 추가본
        #백업
        "14": cisco_backup_vtp,
        "15": cisco_backup_trunk,
        "16": cisco_backup_vlan,
        "17": cisco_backup_stp,

        #vtp 설정
        "18": vtp_setting,

        #trunk 설정
        "19": trunk_setting,

        "20": vlan_edit,
        "21": vlan_access,

        "22": stp_setting,
        "23": inter_vlan
    }

    while True :

        select = input("""작업을 선택하세요.\n
1. 장치 전체 세팅값 백업(run,vtp,stp,trunk,vlan)
2. 세팅 전체 복원

3. 인터페이스 IP 일괄설정 (파일)
4. 인터페이스 IP 프리셋 등록

5. Route 일괄등록 (파일)
6. Route 프리셋 등록
7. Route 개별 등록

8. NAT 설정
9. NAT 복원

10. DHCP 설정 저장
11. DHCP 설정 적용
12. DHCP 복원

13. SVI 설정

14. vtp 설정값 백업
15. trunk 설정값 백업
16. 스위치 포트 vlan 설정값 백업
17. stp 설정값 백업

18. vtp 설정
19. trunk 설정
20. vlan 생성 및 삭제
21. vlan 포트 지정
22. stp blk포트 설정(priority 수정)
23. 라우터 inter vlan 설정

0. 설정 종료

선택: """)

        if select == "0":
            cli.disconnect()
            print("장비 연결을 종료합니다.")
            break

        elif select not in menu:
            print("잘못된 입력입니다. 번호를 다시 입력해 주세요.")
            continue

        func = menu.get(select)

        # [핵심 수정] device_info가 필요한 모든 백업 함수들(1번, 14~17번)에게 두 인자를 모두 전달하도록 수정
        if select in ["1", "14", "15", "16", "17"]:
            func(cli, device_info)

        # 프리셋 생성 함수 (장비 연결 불필요)
        elif select in ["4", "6"]:
            func()

        # 일반 Cisco 설정 함수 (cli만 전달)
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
    14. http 웹 서비스 설치 및 설정
    #15. index.html 백업(미완성)
    #16. index.html 적용(미완성)


    
    0. 종료
    선택: """))
    return res


#ip 정보 백업(파일생성)

# DHCP YAML 생성
def ubt_create_dhcp_yaml(interface):

    yaml_content = (
        "network:\n"
        "  version: 2\n"
        "  ethernets:\n"
        "    " + interface + ":\n"
        "      dhcp4: true\n"
    )

    return yaml_content


# STATIC YAML 생성
def ubt_create_static_yaml(interface):

    ip_addr = input("할당할 IP/서브넷(예: 192.168.1.100/24): ")
    gateway = input("게이트웨이(예: 192.168.1.1): ")
    dns = "8.8.8.8"

    yaml_content = (
        "network:\n"
        "  version: 2\n"
        "  ethernets:\n"
        "    " + interface + ":\n"
        "      addresses:\n"
        "        - " + ip_addr + "\n"
        "      routes:\n"
        "        - to: default\n"
        "          via: " + gateway + "\n"
        "      nameservers:\n"
        "        addresses: [" + dns + "]\n"
        "      dhcp4: false\n"
    )

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
    yaml_cat = "cat /etc/netplan/%s" % yaml[y_num-1]

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

#5_21 ubt nginx 코드










def ubt_install_bind(cli):
    print("[DNS] Bind9 인프라 설치 중...")
    cmd = "sudo apt -y update && sudo apt -y install bind9 bind9utils"
    stdin, stdout, stderr = cli.exec_command(cmd)
    stdout.read() # 설치 완료될 때까지 블로킹 대기

def ubt_zone_set(cli):
    bind_cat = "cat /etc/bind/named.conf.default-zones"
    stdin, stdout, stderr = cli.exec_command(bind_cat)
    output = stdout.read().decode("utf-8")

    cmd = ["vi /etc/bind/named.conf.default-zones",
"""
zone "inssa" {
        type master;
        file "/etc/bind/db.inssa";
};
"""]
    cli.exec_command(cmd)

    reload_cmd = "systemctl reload named"
    cli.exec_command(reload_cmd)


def ubt_add_zone(username):
    ip = input("DNS IP를 입력하세요: ")
    bind_cat = "cat /etc/bind/db.local"
    stdin, stdout, stderr = cli.exec_command(bind_cat)
    output = stdout.read().decode("utf-8")

    cmd = ["vi /etc/bind/db.local",
f"""
{username}\tIN\tA\t{ip}
};
"""]
    cli.exec_command(cmd)
    
    reload_cmd = "systemctl reload named"
    cli.exec_command(reload_cmd)

def ubt_nginx_set(cli, username):
vhost_config_path = f"/etc/nginx/sites-enabled/inssa.conf"
    
    nginx_config = f"""server {{
    listen 80;
    server_name {username}.inssa.com;

    root /home/{username};
    index index.html;

    location / {{
        try_files $uri $uri/ =404;
    }}
}}"""

    nginx_cat = f"cat {vhost_config_path}"
    stdin, stdout, stderr = cli.exec_command(nginx_cat)
    output = stdout.read().decode("utf-8")

    cmd = [f"vim {vhost_config_path}",nginx_config]
    cli.exec_command(cmd)
    print(f"Nginx 설정 내용 추가 완료")

    reload_cmd = "systemctl reload nginx"
    cli.exec_command(reload_cmd)
    print("Nginx 서비스 리로드 완료!")

def ubt_html_set(cli):
    username = input("유저를 선택해주세요 (home 디렉토리 명과 같아야 합니다!!!) : ").strip
    code = input("HTML 코드를 넣으세요: ").strip()

    html_cmd = [f"vim /home/{username}/index.html",code]
    
    stdin, stdout, stderr = cli.exec_command(html_cmd)
    
    # 에러 체크를 위한 로깅
    err = stderr.read().decode("utf-8")
    if err:
        print("에러 발생: %s"%err)
        return
        
    print("생성 완료!")

    ubt_nginx_set(cli, username)
    ubt_add_zone(cli,username)

def add_user(cli):
    username = input("username을 입력해주세요 : ").strip()
    user_pw = input("user password를 입력해주세요 : ").strip()
    cmd = [f"sudo adduser -m {username}",
           f"passwd {username}",
           user_pw,
           user_pw]

    stdin, stdout, stderr = cli.exec_command(cmd)
    err = stderr.read().decode("utf-8")
    if (!err):
        print("home 디렉토리에 %s 폴더가 생성되었습니다. 유저 추가 완료!"%username)








    
def ubt_run_cmd(cli, shell, cmd):

    firewall_meth = [
        "systemctl disable --now ufw",
        "systemctl status ufw",
        # Ubuntu는 보통 SELinux가 없으므로 아래 두 줄은 필요 시에만 사용 (없으면 에러 발생 가능)
        #"if [ -f /etc/selinux/config ]; then sed -i 's/^SELINUX=enforcing/SELINUX=disabled/' /etc/selinux/config; fi",
        #"command -v setenforce >/dev/null && setenforce 0 || echo 'SELinux not found'",
        "init 6"
    ]

    package_update_meth = [
        "rm /var/lib/apt/lists/lock",
        "rm /var/cache/apt/archives/lock",
        "rm /var/lib/dpkg/lock*",
        "dpkg --configure -a",
        "apt update",
        "apt update && apt -y upgrade"]

    package_setting_meth = [
        "apt upgrade",
        "apt -y install software-properties-common wget vim libstdc++6 tar gzip build-essential",
        # Ubuntu는 crb 설정이 필요 없으므로 생략하고 기본 패키지 업데이트만 진행
        "apt -y update && apt -y upgrade"
    ]

    #miniconda_meth = [
    #    "wget https://www.ubiedu.co.kr/Miniconda3-latest-Linux-x86_64.sh",

    miniconda_meth = [

        "wget -O Miniconda3.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh",
    
        "chmod +x Miniconda3.sh",
    
        "./Miniconda3.sh -b -p /root/miniconda3",

        "echo 'export PATH=/root/miniconda3/bin:$PATH' > /etc/profile.d/miniconda.sh",
    
        "chmod +x /etc/profile.d/miniconda.sh",
        "export PATH=/root/miniconda3/bin:$PATH",

        "/root/miniconda3/bin/conda config --set auto_activate_base false",

        "/root/miniconda3/bin/conda config --add channels defaults",
        "/root/miniconda3/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main",

        "/root/miniconda3/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r",

        "/root/miniconda3/bin/conda install -y jupyter jupyterlab pip ipykernel",

        "/root/miniconda3/bin/pip install --upgrade pip",

        "/root/miniconda3/bin/pip install paramiko",

        "/root/miniconda3/bin/pip install netmiko",
        
        "/root/miniconda3/bin/conda install -y -c conda-forge types-cryptography",

        
        
#        "wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh", # 학원 사이트 대신 공식 url 사용.
#        "chmod u+x Miniconda3-latest-Linux-x86_64.sh",
#        "./Miniconda3-latest-Linux-x86_64.sh -b -p /root/miniconda3", 
#        "sed -i '$a export PATH=$PATH:/root/miniconda3/bin' /etc/bash.bashrc", # Ubuntu 전역 경로
#        "/root/miniconda3/bin/conda config --set auto_activate false", 
#        "/root/miniconda3/bin/conda config --add channels defaults",
#        "/root/miniconda3/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main",
#        "/root/miniconda3/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r",
#        "/root/miniconda3/bin/conda install jupyter -y"
    ]

    jupyternotebook_meth = [

        # expect 설치
        "apt -y install expect",

        # jupyter 비밀번호 설정
        r"""expect -c 'spawn /root/miniconda3/bin/jupyter notebook password; expect "Enter password:"; send "asd123!@\r"; expect "Verify password:"; send "asd123!@\r"; expect eof'""",

        # systemd 서비스 생성
        """cat <<EOF > /etc/systemd/system/jupyter.service
[Unit]
Description=Jupyter Notebook Service
After=network.target

[Service]
Type=simple
Environment="PATH=/root/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/root/miniconda3/bin/jupyter notebook --allow-root --ip=0.0.0.0 --port=8080 --no-browser
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF""",

        # systemd 적용
        "systemctl daemon-reload",

        # 서비스 등록
        "systemctl enable jupyter.service",

        # 서비스 시작
        "systemctl restart jupyter.service",

        # 상태 확인
        "systemctl status jupyter.service --no-pager",

        # 포트 확인
        "ss -lntp | grep 8080"
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
            14: ubt_html_set,
        }

    if cmd in [7, 8]:

        # 1. 인터페이스 이름 가져오기
        stdin, stdout, stderr = cli.exec_command(
            "ip -o link show | awk -F': ' '{print $2}' | grep -v '^lo$' | head -n1"
        )

        interface = stdout.read().decode("utf-8").strip()

        if interface == "":
            print("인터페이스 정보를 불러오지 못했습니다.")
            return

        print("선택된 인터페이스:", interface)


        # 2. netplan yaml 파일 가져오기
        stdin, stdout, stderr = cli.exec_command(
            "ls /etc/netplan | grep '.yaml$' | head -n1"
        )

        target_file = stdout.read().decode("utf-8").strip()

        if target_file == "":
            print("netplan yaml 파일을 찾지 못했습니다.")
            return

        print("선택된 netplan 파일:", target_file)


        # 3. yaml 내용 생성
        if cmd == 7:
            new_yaml = ubt_create_dhcp_yaml(interface)
            print(interface + " 네트워크를 DHCP로 전환합니다.")
        else:
            new_yaml = ubt_create_static_yaml(interface)
            print(interface + " 네트워크를 정적 IP로 전환합니다.")


        # 4. 임시 파일로 업로드 후 이동
        sftp = cli.open_sftp()

        file = sftp.file("/tmp/netplan_auto.yaml", "w")
        file.write(new_yaml)
        file.close()

        sftp.close()


        # 5. netplan 적용
        apply_cmd = (
            "cp /etc/netplan/" + target_file + " /etc/netplan/" + target_file + ".bak && "
            "mv /tmp/netplan_auto.yaml /etc/netplan/" + target_file + " && "
            "chmod 600 /etc/netplan/" + target_file + " && "
            "netplan apply"
        )

        stdin, stdout, stderr = cli.exec_command(apply_cmd)

        output = stdout.read().decode("utf-8").strip()
        error = stderr.read().decode("utf-8").strip()

        if output:
            print("[결과]", output)

        if error:
            print("[알림/에러]", error)

        print("netplan apply가 실행되었습니다.")
        return
    
    if (cmd == 13):
        ubt_package_check_install(cli)
        return

    if (cmd == 14):
        ubt_html_set(cli)
        return

    for i in cmd_dict[cmd]:
        print("-> 실행 중: %s" % i)

        if i == "init 6":
            print("시스템을 재부팅합니다. 연결이 끊어집니다.")
            cli.exec_command(i)
            time.sleep(2)
            break

        stdin, stdout, stderr = cli.exec_command(i)

        output = stdout.read().decode("utf-8").strip()
        error = stderr.read().decode("utf-8").strip()

        if output:
            print("[결과]\n%s" % output)

        if error:
            print("[알림/에러]\n%s" % error)
   
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

        if select not in range(0,15):
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


#---- 왕현 우분투 nginx

import time

def ubt_install_bind(cli):
    print("[DNS] Bind9 인프라 설치 중...")
    cmd = "sudo apt -y update && sudo apt -y install bind9 bind9utils"
    stdin, stdout, stderr = cli.exec_command(cmd)
    stdout.read() # 설치 완료될 때까지 블로킹 대기

def ubt_zone_set(cli):
    vhost_zone_path = "/etc/bind/named.conf.default-zones"
    
    # [READ] 기존 구역 설정 파일 내용 긁어오기
    stdin, stdout, stderr = cli.exec_command(f"cat {vhost_zone_path}")
    existing_zone = stdout.read().decode("utf-8")
    
    new_zone_config = """
zone "inssa.com" {
    type master;
    file "/etc/bind/db.inssa";
};
"""
    # 아키텍처: 기존 내용 + 새 내용 결합
    full_zone_config = existing_zone.rstrip() + "\n" + new_zone_config

    cmd = f"sudo tee {vhost_zone_path} << 'EOF'\n{full_zone_config}\nEOF"
    cli.exec_command(cmd)

    current_serial = input("Serial 설정을 위해 오늘의 날짜를 정해주세요!!(ex: 26052101):").strip()
    
    db_init_cmd = f"""sudo tee /etc/bind/db.inssa << 'EOF'
$TTL    604800
@       IN      SOA     ns.inssa.com. root.inssa.com. (
                              {current_serial}         ; Serial (동적 생성)
                         604800         ; Refresh
                          86400         ; Retry
                        2419200         ; Expire
                         604800 )       ; Negative Cache
;
@       IN      NS      ns.inssa.com.
ns      IN      A       {ubt_dns_ip}
EOF"""
    cli.exec_command(db_init_cmd)
    
    cli.exec_command("sudo systemctl reload named")
    print("[DNS] 메인 Zone 도메인 설정 완료!")

def ubt_add_zone(cli, username):
    global ubt_dns_ip
    ubt_dns_ip = input(f"[{username}]에게 할당할 DNS IP를 입력하세요: ").strip()
    db_path = "/etc/bind/db.inssa"
    
    # [READ] 기존 db.inssa 레코드 내용 긁어오기
    stdin, stdout, stderr = cli.exec_command(f"cat {db_path}")
    existing_db = stdout.read().decode("utf-8")
    
    # [APPEND] 기존 내용 밑에 유저용 A 레코드 추가
    new_record = f"{username}\tIN\tA\t{ubt_dns_ip}"
    full_db = existing_db.rstrip() + "\n" + new_record

    # [WRITE] 반영
    cmd = f"sudo tee {db_path} << 'EOF'\n{full_db}\nEOF"
    cli.exec_command(cmd)
    
    cli.exec_command("sudo systemctl reload named")
    print(f"[DNS] {username}.inssa.com -> {ubt_dns_ip} 레코드 누적 추가 완료!")

def ubt_nginx_set(cli, username):
    vhost_config_path = "/etc/nginx/sites-enabled/inssa.conf"
    
    # 파일이 없을 때를 대비해 초기 파일 확보
    cli.exec_command(f"sudo touch {vhost_config_path}")
    
    # [READ] 기존 가상 호스트 내용 긁어오기
    stdin, stdout, stderr = cli.exec_command(f"cat {vhost_config_path}")
    existing_nginx = stdout.read().decode("utf-8")
    
    # 파이썬 f-string 중괄호 충돌 방지를 위해 {{ }} 사용
    new_nginx_config = f"""server {{
    listen 80;
    server_name {username}.inssa.com;

    root /home/{username};
    index index.html;

    location / {{
        try_files $uri $uri/ =404;
    }}
}}"""

    # [APPEND] 하단 결합
    if existing_nginx.strip():
        full_nginx = existing_nginx.rstrip() + "\n\n" + new_nginx_config
    else:
        full_nginx = new_nginx_config

    # [WRITE] 안전하게 스트리밍 주입
    cmd = f"sudo tee {vhost_config_path} << 'EOF'\n{full_nginx}\nEOF"
    cli.exec_command(cmd)
    print(f"[NGINX] {username}.inssa.com 가상호스트 블록 하단 갱신 완료")

    cli.exec_command("sudo systemctl reload nginx")
    print("[NGINX] 서비스 리로드 완료!")

def ubt_html_set(cli):
    username = input("유저를 선택해주세요 (home 디렉토리 명과 같아야 합니다!!!) : ").strip()
    code = input("HTML 코드를 넣으세요: ").strip()

    html_path = f"/home/{username}/index.html"
    
    # 사용자가 입력한 HTML 코드를 해당 홈 디렉토리에 생성
    cmd = f"sudo tee {html_path} << 'EOF'\n{code}\nEOF"
    stdin, stdout, stderr = cli.exec_command(cmd)
    
    err = stderr.read().decode("utf-8")
    if err:
        print(f"에러 발생: {err}")
        return
        
    print(f"[HTML] {username} 계정의 index.html 파일 저장 완료!")

    # 연동 인프라 순차 트리거
    ubt_nginx_set(cli, username)
    ubt_add_zone(cli, username)

def ubt_add_user(cli):
    username = input("username을 입력해주세요 : ").strip()
    user_pw = input("user password를 입력해주세요 : ").strip()
    
    # 우분투 adduser 자동화 생성을 위한 스크립팅 방식 전환
    # --disabled-password로 비대화형 생성을 유도한 뒤, chpasswd로 한 번에 패스워드 주입
    cmd = f"""sudo adduser --disabled-password --gecos "" {username} && echo "{username}:{user_pw}" | sudo chpasswd """

    stdin, stdout, stderr = cli.exec_command(cmd)
    err = stderr.read().decode("utf-8")
    
    if not err:
        print(f"[USER] home 디렉토리에 /home/{username} 폴더가 생성되었습니다. 유저 추가 완료!")
    else:
        print(f"[USER ERROR] 계정 생성 실패: {err}")

# ---
