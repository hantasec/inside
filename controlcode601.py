import os
import sys
import time
import paramiko
import re
from netmiko import ConnectHandler

# 경로 설정
path = "./setting"
dev_path = path + "/devinfo"
backup_path = path + "/backup"
ip_path = path + "/ip"
route_path = path + "/route"
dhcp_path = path + "/dhcp"
html_index_path = path + "/index"
raid_path = path + "/raid"


# ============================================================
# 공통 유틸리티
# ============================================================

def cli_error_check(stdout, stderr):
    output = stdout.read().decode("utf-8").strip()
    error = stderr.read().decode("utf-8").strip()

    if output:
        print(output)

    if error:
        print("[알림/에러]", error)

    return output, error


# ============================================================
# 장비 정보 관리 (계정 생성 / 선택 / 접속)
# ============================================================

def create_dev_info():
    data = ""
    dev_type = {
        '1': "R",
        '2': "SWI",
        '3': "ROC",
        '4': "UBT",
    }

    type = input("계정정보생성 장치 종류 선택:\n[ 1.라우터 ]\n[ 2.스위치 ]\n[ 3.록키  ]\n[ 4.우분투 ]\n")

    if type not in ['1', '2', '3', '4']:
        print("잘못된 입력입니다. 장치 타입에 해당하는 숫자로 선택해 주세요.")
        return

    name = input("장치를 구분할 이름을 설정해주세요.")
    host_ip = input("생성할 장비의 IP 주소를 입력하세요: ")
    username = input("생성할 장비의 계정 이름을 입력하세요: ")
    password = input("생성할 장비의 비밀번호를 입력하세요: ")

    if type == '1' or type == '2':
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
            % (dev_type[type], name, host_ip, username, password)
        )

    elif type == '3' or type == '4':
        data = (
            "type=%s\n"
            "name=%s\n"
            "host=%s\n"
            "username=%s\n"
            "password=%s\n"
            "port=22\n"
            % (dev_type[type], name, host_ip, username, password)
        )

    os.makedirs(dev_path, exist_ok=True)
    with open("%s/%s_%s.txt" % (dev_path, dev_type[type], name), 'w', encoding='utf-8') as devinfo:
        devinfo.write(data)

    print("계정정보 생성이 완료되었습니다.\n%s/%s_%s.txt" % (dev_path, dev_type[type], name))


def select_dev():
    os.makedirs(dev_path, exist_ok=True)
    device_list = os.listdir(dev_path)
    for i in range(len(device_list)):
        device_list[i] = device_list[i].replace(".txt", "")

    print("접속할 계정을 선택해 주세요.")
    print(device_list)
    file_name = input(":")

    if file_name not in device_list:
        print("%s? 존재하지 않는 계정입니다. 계정을 등록하고 사용해 주세요." % file_name)
        return

    with open("%s/%s.txt" % (dev_path, file_name), "r", encoding="utf-8") as data:
        dev_info = dict()
        datas = data.readlines()
        for i in datas:
            key, value = i.strip().split("=")
            dev_info[key] = value

    print(dev_info)
    return dev_info


def connect_dev():
    dev_info = select_dev()

    if not dev_info:
        return

    dev_menu = {
        "R": cisco_menu,
        "SWI": cisco_menu,
        "ROC": roc_menu,
        "UBT": ubt_menu,
    }

    func = dev_menu.get(dev_info["type"])

    if func:
        func(dev_info)
    else:
        print("지원하지 않는 장비 타입입니다.")
        return


# ============================================================
# 리눅스 공통 연결
# ============================================================

def connect_linux(device_info):
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


# ============================================================
# Rocky Linux 유틸리티
# ============================================================

def roc_run_command(cli, cmd):
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


def roc_path_check(cli, file):
    cmd = "[ -e '%s' ] && echo 'y' || echo 'n'" % file
    stdin, stdout, stderr = cli.exec_command(cmd)
    output = stdout.read().decode('utf-8').strip()
    if output == 'y':
        print("%s 가 존재합니다." % file)
        return True
    else:
        print("%s 가 존재하지 않습니다." % file)
        return False


def roc_user_add(cli, username=""):
    if username == "":
        username = input("생성할 username 을 입력하세요 :")
    passwd = input("생성할 passwd를 입력하세요:")
    cmd = [
        "id '%s' >/dev/null 2>&1 || useradd -m '%s'" % (username, username),
        "echo '%s:%s' | chpasswd" % (username, passwd),
        "chmod 755 /home/%s" % username,
    ]
    roc_run_command(cli, cmd)


def roc_index_html_create(cli, user):
    cmd = """chmod 755 /home/%s
cat << 'EOF' > /home/%s/index.html
created.
EOF
chmod 755 /home/%s/index.html
chown %s:%s /home/%s/index.html
ls -l /home/%s/index.html
""" % (user, user, user, user, user, user, user)

    stdin, stdout, stderr = cli.exec_command(cmd)
    cli_error_check(stdout, stderr)
    print("index.html 생성 완료.")


# ============================================================
# Rocky Linux 시스템 설정
# ============================================================

def roc_firewall_disable(cli):
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
    if not error:
        print("방화벽 해제 커맨드 생성 완료.")


def roc_package_update(cli):
    cmd = [
        "dnf -y update && dnf -y upgrade"
    ]
    roc_run_command(cli, cmd)


def roc_package_setting(cli):
    cmd = [
        "dnf -y install epel-release wget vim libstdc++ tar gzip expect",
        "dnf makecache",
        "dnf config-manager --set-enabled crb",
        "dnf -y update && dnf -y upgrade"
    ]
    roc_run_command(cli, cmd)


def roc_ip_set(cli):
    ens = input("설정할 인터페이스를 입력하세요.(ex:ens160):")
    restart = "nmcli connection down" + " " + ens + " " + ";" + "nmcli connection up" + " " + ens
    ipsetting = input("설정할 아이피 주소를 입력하세요:")
    fixsetting = input("설정할 프리픽스를 입력하세요(예:/16):")
    stdin, stdout, stderr = cli.exec_command("nmcli connection modify " + ens + " ipv4.addresses " + ipsetting + fixsetting)
    print("ip가 변경됩니다... 프로그램이 종료됩니다.")
    stdin, stdout, stderr = cli.exec_command(restart)
    sys.exit()


def roc_gate_set(cli):
    ens = input("설정할 인터페이스를 입력하세요.(ex:ens160):")
    restart = "nmcli connection down" + " " + ens + " " + ";" + "nmcli connection up" + " " + ens
    gatesetting = input("설정할 게이트웨이 주소를 입력하세요:")
    stdin, stdout, stderr = cli.exec_command("nmcli connection modify" + " " + ens + " " + "ipv4.gateway" + " " + gatesetting)
    print("ip가 변경됩니다... 프로그램이 종료됩니다.")
    stdin, stdout, stderr = cli.exec_command(restart)
    sys.exit()


def roc_check_dev(cli):
    enable_list = ""
    cmd = "lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINTS"
    filename = "sata_list"
    stdin, stdout, stderr = cli.exec_command(cmd)
    result = stdout.read().decode("utf-8").strip()

    lines = result.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r'(^sd[a-z])', line)
        if not m:
            continue

        next_line = lines[i + 1]
        if not re.search(r'^[├└]', next_line):
            dev = str(line)
            enable_list = enable_list + line + "\n"

    with open("%s/%s.txt" % (raid_path, filename), "w", encoding="utf-8") as file:
        file.write(enable_list)
    print("현재 로키 리눅스에서 레이드 구성이 가능한 장치의 리스트는 다음과 같습니다. \n%s" % enable_list)


# ============================================================
# Rocky Linux Miniconda / Jupyter
# ============================================================

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
    roc_run_command(cli, cmd)


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
    roc_run_command(cli, cmd)


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
    roc_run_command(cli, cmd)


# ============================================================
# Rocky Linux 웹 서버 (httpd)
# ============================================================

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

    html_content = "<h1>Welcome to %s!</h1>" % server_name
    target_index_path = "%s/index.html" % document_root

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
        print("index.html 소유권을 %s 계정으로 변경 완료" % owner_user)

    roc_httpd_healthcheck(cli)

    print("Rocky httpd 설정 완료")


def roc_httpd_healthcheck(cli):
    stdin, stdout, stderr = cli.exec_command("httpd -t")
    httpd_check, error = cli_error_check(stdout, stderr)
    check_result = httpd_check + error

    print("httpd 설정 검사 결과:\n%s" % check_result)
    if "Syntax OK" not in check_result:
        print("httpd 설정 오류 발생. 서비스를 재시작하지 않습니다.")
        return

    stdin, stdout, stderr = cli.exec_command("systemctl restart httpd")
    cli_error_check(stdout, stderr)
    print("httpd 서버 재시작 완료")


def roc_index_backup(cli):
    os.makedirs(html_index_path, exist_ok=True)
    cmd = "cat /etc/httpd/conf/httpd.conf | grep ^DocumentRoot"
    stdin, stdout, stderr = cli.exec_command(cmd)
    tmp = stdout.read().decode('utf-8').strip().split()
    doc_root = tmp[1].strip("\"")
    cmd = "cat %s/index.html" % doc_root
    stdin, stdout, stderr = cli.exec_command(cmd)
    output = stdout.read().decode('utf-8').strip()

    filename = input("저장할 파일의 이름을 입력하세요:")
    path2 = html_index_path + '/' + filename + '.txt'
    file_new = open(path2, "w", encoding="utf-8")
    file_new.write(output)
    file_new.close()
    print("파일백업이 완료되었습니다.")


# ============================================================
# Rocky Linux DNS (BIND)
# ============================================================

def roc_dns_allow(cli):
    cmd = """sed -i 's/^[[:space:]]*listen-on port.*/        listen-on port 53 { any; };/' /etc/named.conf &&
sed -i 's/^[[:space:]]*allow-query.*/        allow-query     { any; };/' /etc/named.conf """

    stdin, stdout, stderr = cli.exec_command(cmd)
    cli_error_check(stdout, stderr)
    print("/etc/named.conf port, query allow any 설정 완료.")
    return


def roc_zone_add(cli, teamname, types):
    cmd = """if grep -q 'zone "%s.com"' /etc/named.rfc1912.zones; then
    echo '[중복] zone 존재'
else
cat << EOF >> /etc/named.rfc1912.zones

zone "%s.com" IN {
    type %s;
    file "%s.com.zone";
    allow-update { none; };
};

EOF
fi
""" % (teamname, teamname, types, teamname)

    stdin, stdout, stderr = cli.exec_command(cmd)
    output = stdout.read().decode('utf-8').strip()
    error = stderr.read().decode('utf-8').strip()
    if output:
        print(output)

    if "[중복]" in output:
        return False

    if error:
        print("[오류]", error)
        return False

    print("zone 추가 완료.")
    return True


def roc_zone_create(cli, teamname, ip):
    serial = input("존파일의 시리얼 번호를 입력하세요. (ex:26052201): ")
    zone_file = "/var/named/%s.com.zone" % teamname

    zone = """$TTL 1D
@   IN SOA  ns.%s.com. root.%s.com. (
        %s      ; serial
        1D      ; refresh
        1H      ; retry
        1W      ; expire
        3H )    ; minimum

    IN NS   ns.%s.com.
ns  IN A    %s
@   IN A    %s
""" % (teamname, teamname, serial, teamname, ip, ip)

    cmd = """if [ -e '%s' ]; then
    echo '[중복] %s 파일이 이미 존재합니다.'
    exit 1
else
    cat << 'EOF' > '%s'
%s
EOF
    chown root:named '%s'
    chmod 640 '%s'
    named-checkzone %s.com '%s'
fi
""" % (zone_file, zone_file, zone_file, zone, zone_file, zone_file, teamname, zone_file)

    stdin, stdout, stderr = cli.exec_command(cmd)
    output, error = cli_error_check(stdout, stderr)

    if "[중복]" in output:
        return False

    if "not loaded" in output:
        print("zone 파일 검증 실패")
        return False

    print("%s 생성 완료" % zone_file)
    return True


def roc_zone_add_a_record(cli, teamname, user, ip):
    zone_file = "/var/named/%s.com.zone" % teamname

    cmd = """if grep -q '^%s[[:space:]]\\+IN[[:space:]]\\+A' '%s'; then
    echo '[중복] %s A 레코드가 이미 존재합니다.'
else
    echo '%s  IN A    %s' >> '%s'
    named-checkzone %s.com '%s'
fi
""" % (user, zone_file, user, user, ip, zone_file, teamname, zone_file)

    stdin, stdout, stderr = cli.exec_command(cmd)
    output, error = cli_error_check(stdout, stderr)

    if "not loaded" in output:
        return False

    return True


# ============================================================
# Rocky Linux VirtualHost
# ============================================================

def roc_vh_create(cli, user, teamname):
    servername = "%s.%s.com" % (user, teamname)

    vhost = """
<VirtualHost *:80>
    ServerName %s
    DocumentRoot "/home/%s"
    <Directory "/home/%s">
        Require all granted
    </Directory>
</VirtualHost>
""" % (servername, user, user)

    cmd = """if grep -q 'ServerName[[:space:]]\\+%s' /etc/httpd/conf.d/vhost.conf 2>/dev/null; then
    echo '[중복] %s VirtualHost가 이미 존재합니다.'
else
    cat << 'EOF' >> /etc/httpd/conf.d/vhost.conf
%s
EOF
    httpd -t
fi
""" % (servername, servername, vhost)

    stdin, stdout, stderr = cli.exec_command(cmd)
    cli_error_check(stdout, stderr)


# ============================================================
# Rocky Linux Web+DNS 통합 설정
# ============================================================

def roc_http_dns_install(cli):
    print("\nhttpd, bind 설치 및 서비스 활성화 중...")

    cmd = '''
dnf -y install httpd bind bind-utils &&
systemctl enable --now httpd &&
systemctl enable --now named &&
systemctl status httpd --no-pager &&
systemctl status named --no-pager
'''

    stdin, stdout, stderr = cli.exec_command(cmd)
    cli_error_check(stdout, stderr)
    print("httpd, bind 설치 및 서비스 활성화 완료")


def roc_web_dns_set(cli):
    teamname = input("팀명 입력: ")
    server_ip = input("서버 IP 입력: ")

    roc_dns_allow(cli)

    result = roc_zone_create(cli, teamname, server_ip)
    if not result:
        return

    roc_zone_add(cli, teamname, "master")

    while True:
        user = input("사용자명 입력: ")

        route = "/home/%s" % user

        if not roc_path_check(cli, route):
            roc_user_add(cli, user)

        roc_vh_create(cli, user, teamname)
        roc_index_html_create(cli, user)
        roc_zone_add_a_record(cli, teamname, user, server_ip)

        end = input("사용자를 더 추가하시겠습니까? (y/n): ")

        if end.lower() == "n":
            break

    roc_httpd_healthcheck(cli)

    roc_run_command(cli, [
        "named-checkconf",
        "named-checkzone %s.com /var/named/%s.com.zone" % (teamname, teamname),
        "systemctl restart named"
    ])


# ============================================================
# Rocky Linux PHP / MariaDB / phpMyAdmin
# ============================================================

def roc_php_set(cli):
    cmd = """dnf install https://rpms.remirepo.net/enterprise/remi-release-9.rpm &&
dnf config-manager --set-enabled remi &&
dnf -y module install php:remi-8.4 &&
dnf module enable php:remi-8.4 &&
php --version &&
dnf --disablerepo=remi-safe update &&
dnf -y install libjpeg* libpng* freetype* gd-* gcc gcc-c++ gdbm-devel giflib* &&
dnf -y install php php-bcmath php-cli php-common php-devel php-mbstring php-odbc php-process &&
dnf -y install php-gd libpng-devel php-mysql php-gettext php-pear php-xml php-xmlrpc &&
dnf -y install php-zip php-opcache php-mysqlnd php-fpm php*-zip php-intl php-pdo &&
dnf -y install php-bcmath libzip-devel php-pear zlib-devel &&
dnf -y update
"""
    stdin, stdout, stderr = cli.exec_command(cmd)
    output, error = cli_error_check(stdout, stderr)

    if not error:
        print("PHP 설치 완료.")


def roc_mariadb_char_set(cli):
    cmd = """cat <<EOF >> /etc/my.cnf.d/mariadb-server.cnf
[client]
default-character-set = utf8mb4
EOF
sed -i "/^\\[mysqld\\]/a character-set-server = utf8mb4" /etc/my.cnf.d/mariadb-server.cnf
"""
    stdin, stdout, stderr = cli.exec_command(cmd)
    output, error = cli_error_check(stdout, stderr)

    if not error:
        print("MariaDB charset 설정 완료")


def roc_mariadb_secure(cli):
    sql = f"""
ALTER USER 'root'@'localhost'
IDENTIFIED VIA unix_socket;

DELETE FROM mysql.user
WHERE User='';

DROP DATABASE IF EXISTS test;

DELETE FROM mysql.db
WHERE Db='test'
OR Db LIKE 'test\\_%';

ALTER USER 'root'@'localhost'
IDENTIFIED BY 'asd123!@';

FLUSH PRIVILEGES;
"""

    cmd = f'''sudo mysql -e "{sql}"

echo ""
echo "========= 설정 확인 ========="

sudo mysql -e "
SELECT User,Host,plugin
FROM mysql.user;

SHOW DATABASES;
"

echo ""
echo "========= 로그인 테스트 ========="

mysql -u root -p 'asd123!@' -e "
SELECT 'LOGIN SUCCESS';
"
'''

    stdin, stdout, stderr = cli.exec_command(cmd)
    output, error = cli_error_check(stdout, stderr)

    if not error:
        print("MariaDB 보안 설정 완료")


def roc_phpmyadmin_set(cli):
    cmd = """dnf -y install phpmyadmin
systemctl restart httpd
systemctl restart php-fpm
chown -R apache:apache /usr/share/phpMyAdmin
sed -i "s/cookie';$/http';/" /etc/phpMyAdmin/config.inc.php &&
sed -i '/<Directory \\/usr\\/share\\/phpMyAdmin\\/>/,/<\\/Directory>/ s|Require .*|Require all granted|' /etc/httpd/conf.d/phpMyAdmin.conf
systemctl restart httpd
"""
    stdin, stdout, stderr = cli.exec_command(cmd)
    output, error = cli_error_check(stdout, stderr)

    if not error:
        print("phpMyAdmin 설정 완료")


def roc_mariadb_add_user(cli, username=""):
    if username == "":
        username = input("생성할 DB 계정명 : ")

    passwd = input("비밀번호 : ")

    sql = """
CREATE USER IF NOT EXISTS '%s'@'%%'
IDENTIFIED BY '%s';

CREATE DATABASE IF NOT EXISTS %s;

GRANT ALL PRIVILEGES
ON %s.*
TO '%s'@'%%';

FLUSH PRIVILEGES;
""" % (username, passwd, username, username, username)

    cmd = '''mysql -u root -p'asd123!@' -e "%s"

echo ""
echo "========= 생성 결과 ========="

mysql -u root -p'asd123!@' -e "
SELECT User,Host
FROM mysql.user
WHERE User='%s';

SHOW DATABASES LIKE '%s';

SHOW GRANTS FOR '%s'@'%%';
"
''' % (sql, username, username, username)

    stdin, stdout, stderr = cli.exec_command(cmd)
    output, error = cli_error_check(stdout, stderr)

    if not error:
        print("%s DB 계정 생성 완료" % username)


# ============================================================
# Rocky Linux Samba / FTP
# ============================================================

def roc_samba_mounting(cli, ip, smb_dir, mnt_path, username, passwd):
    cred_path = "/etc/samba/cred/"
    cred_file = cred_path + username

    cmd = "dnf -y install samba samba-client samba-common cifs-utils"
    stdin, stdout, stderr = cli.exec_command(cmd)
    output, error = cli_error_check(stdout, stderr)

    cmd = """mkdir -p %s
mkdir -p %s
cat > %s << EOF
username=%s
password=%s
EOF
chmod 600 %s
""" % (cred_path, mnt_path, cred_file, username, passwd, cred_file)

    stdin, stdout, stderr = cli.exec_command(cmd)
    output, error = cli_error_check(stdout, stderr)

    cmd = """grep -q '//%s/%s ' /etc/fstab || echo '//%s/%s %s cifs credentials=%s,iocharset=utf8 0 0' >> /etc/fstab
systemctl daemon-reload
mount -a
""" % (ip, smb_dir, ip, smb_dir, mnt_path, cred_file)

    stdin, stdout, stderr = cli.exec_command(cmd)
    output, error = cli_error_check(stdout, stderr)


def roc_restricted_ftp_setting(cli, user):
    cmd = """dnf -y install vsftpd &&
sed -i 's|^#*write_enable=.*|write_enable=YES|' /etc/vsftpd/vsftpd.conf &&
sed -i 's|^#*userlist_enable=.*|userlist_enable=YES|' /etc/vsftpd/vsftpd.conf &&
sed -i 's|^#*userlist_deny=.*|userlist_deny=NO|' /etc/vsftpd/vsftpd.conf &&
grep -qxF '%s' /etc/vsftpd/user_list || echo '%s' >> /etc/vsftpd/user_list &&
sed -i 's|^.*pam_shells\\.so.*|#auth       required    pam_shells.so|' /etc/pam.d/vsftpd &&
usermod -s /sbin/nologin %s &&
systemctl enable --now vsftpd &&
systemctl restart vsftpd
""" % (user, user, user)

    stdin, stdout, stderr = cli.exec_command(cmd)
    output, error = cli_error_check(stdout, stderr)


# ============================================================
# Rocky Linux 메뉴
# ============================================================

def roc_menu(device_info):
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
        0: 0
    }

    cli = connect_linux(device_info)
    if cli is None:
        print("리눅스 연결 실패로 메뉴를 종료합니다.")
        return

    while True:
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
        0. 종료
        선택: """))

        if select not in cmd_dict:
            print("없는 번호입니다. 다시 입력해 주세요.")
            continue

        if select == 0:
            print("exit")
            break
        else:
            func = cmd_dict[select]
            if func:
                func(cli)

    cli.close()


# ============================================================
# Cisco 공통
# ============================================================

def connect_cisco(device_info):
    conn_info = device_info.copy()
    conn_info.pop("type", None)
    conn_info.pop("name", None)

    conn_info["port"] = int(conn_info["port"])
    conn_info["conn_timeout"] = int(conn_info["conn_timeout"])
    conn_info["auth_timeout"] = int(conn_info["auth_timeout"])
    conn_info["banner_timeout"] = int(conn_info["banner_timeout"])

    print("%s 접속 시도 중 " % conn_info["host"])

    cli = ConnectHandler(**conn_info, global_delay_factor=2)
    cli.enable()
    return cli


def command_cisco(cli, command):
    if isinstance(command, str):
        command = command.splitlines()
    output = cli.send_config_set(command)
    print(output)
    print("장비 설정 적용 완료!")
    return output


# ============================================================
# Cisco 백업 / 복원
# ============================================================

def cisco_backup(cli, device_info):
    os.makedirs(backup_path, exist_ok=True)

    backup_cmds = {
        "run": "show run",
        "vtp": "show vtp status",
        "trunk": "show int trunk",
        "vlan": "show vlan-switch bri",
        "stp": "show spanning-tree bri",
    }

    for suffix, cmd in backup_cmds.items():
        output = cli.send_command(cmd)
        fname = "%s/%s_%s_backup%s.txt" % (
            backup_path,
            device_info["type"],
            device_info["name"],
            "" if suffix == "run" else "_" + suffix
        )
        with open(fname, "w") as file:
            file.write(output)

    print("백업 완료")


def cisco_backup_vtp(cli, device_info):
    os.makedirs(backup_path, exist_ok=True)
    output = cli.send_command("show vtp status")
    with open("%s/%s_%s_backup_vtp.txt" % (backup_path, device_info["type"], device_info["name"]), "w") as file:
        file.write(output)
    print("vtp status 백업 완료")


def cisco_backup_trunk(cli, device_info):
    os.makedirs(backup_path, exist_ok=True)
    output = cli.send_command("show int trunk")
    with open("%s/%s_%s_backup_trunk.txt" % (backup_path, device_info["type"], device_info["name"]), "w") as file:
        file.write(output)
    print("trunk interface 백업 완료")


def cisco_backup_vlan(cli, device_info):
    os.makedirs(backup_path, exist_ok=True)
    output = cli.send_command("show vlan-switch bri")
    with open("%s/%s_%s_backup_vlan.txt" % (backup_path, device_info["type"], device_info["name"]), "w") as file:
        file.write(output)
    print("vlan port brief 백업 완료")


def cisco_backup_stp(cli, device_info):
    os.makedirs(backup_path, exist_ok=True)
    output = cli.send_command("show spanning-tree bri")
    with open("%s/%s_%s_backup_stp.txt" % (backup_path, device_info["type"], device_info["name"]), "w") as file:
        file.write(output)
    print("spanning tree brief 백업 완료")


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

    for line in lines:
        clean_line = line.strip()
        if clean_line.startswith("ip nat inside") or clean_line.startswith("ip nat pool") or clean_line.startswith("access-list"):
            nat_commands.append(clean_line)

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

        if clear_line.startswith("ip dhcp excluded-address"):
            dhcp_cmd.append(clear_line)

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


# ============================================================
# Cisco IP / Route
# ============================================================

def ip_preset():
    cmd = ""
    os.makedirs(ip_path, exist_ok=True)
    name = input("생성할 ip셋의 이름 : ")
    while True:
        cmd += input("인터페이스\t: ")
        cmd += ' ' + input("네트워크\t: ")
        cmd += ' ' + input("서브넷\t: ")
        cmd += '\n'
        if 'n' == input("계속? y/n"):
            break

    with open("%s/%s.txt" % (ip_path, name), "w") as file:
        file.write(cmd)


def ip_setting(cli):
    command = ""
    ip_list = os.listdir(ip_path)
    for i in range(len(ip_list)):
        ip_list[i] = ip_list[i].replace(".txt", "")
    print(ip_list)
    name = input("인터페이스 일괄 등록 ip 파일명을 입력하세요. : ")

    with open("%s/%s.txt" % (ip_path, name), 'r') as f:
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
        command_cisco(cli, command)


def route_preset():
    cmd = ""
    os.makedirs(route_path, exist_ok=True)
    name = input("생성할 route셋의 이름 : ")
    while True:
        cmd += input("목적지 네트워크\t: ")
        cmd += ' ' + input("서브넷\t: ")
        cmd += ' ' + input("게이트웨이\t: ")
        cmd += '\n'
        if 'n' == input("계속? y/n"):
            break

    with open("%s/%s.txt" % (route_path, name), "w") as file:
        file.write(cmd)


def route_setting(cli):
    command = ""
    route_list = os.listdir(route_path)
    for i in range(len(route_list)):
        route_list[i] = route_list[i].replace(".txt", "")
    print(route_list)
    name = input("라우팅 경로 일괄 등록 라우트 파일명을 입력하세요. : ")

    with open("%s/%s.txt" % (route_path, name), 'r') as f:
        lines = f.readlines()

        for route in lines:
            route = route.strip()

            if not route:
                continue

            command += "ip route " + route + "\n"

        print("설정된 값\n" + command)
        command_cisco(cli, command)


def static_router_setting(cli):
    ro_ip_str = input("ip대역 입력: ")
    ro_sub_str = input("서브넷마스크 입력: ")
    ro_gw_str = input("게이트웨이 입력: ")

    command = (
        "ip route "
        + ro_ip_str + " "
        + ro_sub_str + " "
        + ro_gw_str
    )

    command_cisco(cli, command)


# ============================================================
# Cisco NAT
# ============================================================

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


def nat_static(cli):
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


def nat_dynamic(cli):
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


def pat(cli):
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


# ============================================================
# Cisco DHCP / SVI
# ============================================================

def dhcp_setting(cli):
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


def svi_setting(cli):
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


# ============================================================
# Cisco VTP / Trunk / VLAN / STP / Inter-VLAN
# ============================================================

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


def trunk_setting(cli):
    while True:
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
        time.sleep(1)


def vlan_edit(cli):
    while True:
        user_input = input("""1. vlan 추가
2. vlan 삭제

0. 종료
""")
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
            cli.send_config_set(commands)


def vlan_access(cli):
    port_int = input("포트 인터페이스를 입력해주세요 : ").strip()
    vlan = input("몇 번 vlan으로 설정하시겠습니까? : (ex : 10) ").strip()

    commands = [
        f"interface {port_int}",
        "switchport mode access",
        f"switchport access vlan {vlan}"
    ]
    output = cli.send_config_set(commands)
    print(output)


def stp_setting(cli):
    vlan = input("몇 번 vlan으로 설정하시겠습니까? : (ex : 10) ").strip()
    prio = input("priority값을 입력해주세요 : (ex : 4096) ").strip()
    commands = [
        f"spanning-tree vlan {vlan} priority {prio}"
    ]
    output = cli.send_config_set(commands)
    print(output)


def inter_vlan(cli):
    gate_port = input("게이트웨이 포트를 입력해주세요 : (ex : f0/0) ").strip()

    init_commands = [
        f"interface {gate_port}",
        "no shutdown"
    ]
    cli.send_config_set(init_commands)

    while True:
        flag = input("inter vlan을 설정하시겠습니까? : (Y / N) ").strip().upper()
        if flag == "Y":
            vlan_domain = input("vlan 번호(도메인)를 입력하세요 : (ex : f0/0.10 이면 10만 입력): ").strip()
            vlan_gate = input("vlan의 gateway IP를 입력해주세요 : ").strip()
            vlan_mask = input("vlan의 subnet mask를 입력해주세요 : ").strip()

            commands = [
                f"interface {gate_port}.{vlan_domain}",
                f"encapsulation dot1Q {vlan_domain}",
                f"ip address {vlan_gate} {vlan_mask}"
            ]
            output = cli.send_config_set(commands)
            print(output)
        else:
            break


# ============================================================
# Cisco 메뉴
# ============================================================

def cisco_menu(device_info):
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
        "9": nat_restore,
        "10": dhcp_setting,
        "11": dhcp_apply,
        "12": dhcp_restore,
        "13": svi_setting,
        "14": cisco_backup_vtp,
        "15": cisco_backup_trunk,
        "16": cisco_backup_vlan,
        "17": cisco_backup_stp,
        "18": vtp_setting,
        "19": trunk_setting,
        "20": vlan_edit,
        "21": vlan_access,
        "22": stp_setting,
        "23": inter_vlan
    }

    while True:
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

        if select in ["1", "14", "15", "16", "17"]:
            func(cli, device_info)
        elif select in ["4", "6"]:
            func()
        else:
            func(cli)


# ============================================================
# Ubuntu 유틸리티
# ============================================================

def ubt_create_dhcp_yaml(interface):
    yaml_content = (
        "network:\n"
        "  version: 2\n"
        "  ethernets:\n"
        "    " + interface + ":\n"
        "      dhcp4: true\n"
    )
    return yaml_content


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


def ubt_netplan_list_meth(output):
    file = open("netplan_ls", "w", encoding="utf-8")
    file.write(output)
    file.close()

    file = open("netplan_ls", "r", encoding="utf-8")
    global yaml
    yaml = file.read().split()
    file.close()


def ubt_yaml_cat():
    for i in range(len(yaml)):
        print("%d. %s" % (i + 1, yaml[i]))
    global y_num
    y_num = int(input("파일을 선택해주세요 : "))
    yaml_cat = "cat /etc/netplan/%s" % yaml[y_num - 1]


def ubt_make_yaml_cat(output):
    file = open("netplan_cat", "w", encoding="utf-8")
    data = yaml[y_num] + "\n" + output
    file.write(data)
    file.close()


def ubt_ip_a(output):
    file = open("ub_ip_a", "w", encoding="utf-8")
    file.write(output)
    file.close()


def ubt_ip_r(output):
    file = open("ub_ip_r", "w", encoding="utf-8")
    file.write(output)
    file.close()


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


# ============================================================
# Ubuntu 시스템 설정 (httpd / nginx)
# ============================================================

def ubt_httpd_set(cli):
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

    print("[입력] 새로 생성할 'manager' 계정의 비밀번호를 정해주세요.")
    manager_password = input("manager password : ")

    if manager_password.strip() == "":
        print("비밀번호가 입력되지 않았습니다. 스크립트를 종료합니다.")
        return

    print("\n[2/6] manager 유저 생성 및 비밀번호 설정 중...")
    cmd = 'id manager >/dev/null 2>&1 || useradd -m manager; echo "manager:%s" | chpasswd' % manager_password
    stdin, stdout, stderr = cli.exec_command(cmd)
    cli_error_check(stdout, stderr)
    print("manager 유저 생성, 비밀번호 등록 완료")

    print("\n[3/6] apt 패키지 업데이트 및 업그레이드 중... (시간이 다소 소요될 수 있습니다)")
    cmd = "DEBIAN_FRONTEND=noninteractive apt -y update && DEBIAN_FRONTEND=noninteractive apt -y upgrade"
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=300)
    cli_error_check(stdout, stderr)
    print("apt 업데이트 완료")

    print("\n[4/6] Nginx 설치 중...")
    stdin, stdout, stderr = cli.exec_command('DEBIAN_FRONTEND=noninteractive apt -y install nginx', timeout=150)
    cli_error_check(stdout, stderr)
    print("Nginx 설치 완료")

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
    print("Nginx Test 결과:\n%s" % nginx_check)

    stdin, stdout, stderr = cli.exec_command('systemctl restart nginx')
    cli_error_check(stdout, stderr)
    print("Nginx 서버 재시작 완료")

    print("\n--- 모든 작업이 완료되었습니다! ---")
    print("서버가 재부팅되면 SSH 연결이 끊어집니다.")

    stdin, stdout, stderr = cli.exec_command('reboot')
    cli.close()
    print("SSH 연결 종료 및 서버 재부팅 프로세스 시작.")


# ============================================================
# Ubuntu DNS (BIND9)
# ============================================================

def ubt_install_bind(cli):
    print("[DNS] Bind9 인프라 설치 중...")
    cmd = "sudo apt -y update && sudo apt -y install bind9 bind9utils"
    stdin, stdout, stderr = cli.exec_command(cmd)
    stdout.read()  # 설치 완료될 때까지 블로킹 대기


def ubt_zone_set(cli):
    vhost_zone_path = "/etc/bind/named.conf.default-zones"

    stdin, stdout, stderr = cli.exec_command(f"cat {vhost_zone_path}")
    existing_zone = stdout.read().decode("utf-8")

    new_zone_config = """
zone "inssa.com" {
    type master;
    file "/etc/bind/db.inssa";
};
"""
    full_zone_config = existing_zone.rstrip() + "\n" + new_zone_config

    cmd = f"sudo tee {vhost_zone_path} << 'EOF'\n{full_zone_config}\nEOF"
    cli.exec_command(cmd)

    current_serial = input("Serial 설정을 위해 오늘의 날짜를 정해주세요!!(ex: 26052101):").strip()

    db_init_cmd = f"""sudo tee /etc/bind/db.inssa << 'EOF'
$TTL    604800
@       IN      SOA     ns.inssa.com. root.inssa.com. (
                              {current_serial}         ; Serial
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

    stdin, stdout, stderr = cli.exec_command(f"cat {db_path}")
    existing_db = stdout.read().decode("utf-8")

    new_record = f"{username}\tIN\tA\t{ubt_dns_ip}"
    full_db = existing_db.rstrip() + "\n" + new_record

    cmd = f"sudo tee {db_path} << 'EOF'\n{full_db}\nEOF"
    cli.exec_command(cmd)

    cli.exec_command("sudo systemctl reload named")
    print(f"[DNS] {username}.inssa.com -> {ubt_dns_ip} 레코드 누적 추가 완료!")


# ============================================================
# Ubuntu Nginx / HTML / 유저
# ============================================================

def ubt_nginx_set(cli, username):
    vhost_config_path = "/etc/nginx/sites-enabled/inssa.conf"

    cli.exec_command(f"sudo touch {vhost_config_path}")

    stdin, stdout, stderr = cli.exec_command(f"cat {vhost_config_path}")
    existing_nginx = stdout.read().decode("utf-8")

    new_nginx_config = f"""server {{
    listen 80;
    server_name {username}.inssa.com;

    root /home/{username};
    index index.html;

    location / {{
        try_files $uri $uri/ =404;
    }}
}}"""

    if existing_nginx.strip():
        full_nginx = existing_nginx.rstrip() + "\n\n" + new_nginx_config
    else:
        full_nginx = new_nginx_config

    cmd = f"sudo tee {vhost_config_path} << 'EOF'\n{full_nginx}\nEOF"
    cli.exec_command(cmd)
    print(f"[NGINX] {username}.inssa.com 가상호스트 블록 하단 갱신 완료")

    cli.exec_command("sudo systemctl reload nginx")
    print("[NGINX] 서비스 리로드 완료!")


def ubt_html_set(cli):
    username = input("유저를 선택해주세요 (home 디렉토리 명과 같아야 합니다!!!) : ").strip()
    code = input("HTML 코드를 넣으세요: ").strip()

    html_path = f"/home/{username}/index.html"

    cmd = f"sudo tee {html_path} << 'EOF'\n{code}\nEOF"
    stdin, stdout, stderr = cli.exec_command(cmd)

    err = stderr.read().decode("utf-8")
    if err:
        print(f"에러 발생: {err}")
        return

    print(f"[HTML] {username} 계정의 index.html 파일 저장 완료!")

    ubt_nginx_set(cli, username)
    ubt_add_zone(cli, username)


def ubt_add_user(cli):
    username = input("username을 입력해주세요 : ").strip()
    user_pw = input("user password를 입력해주세요 : ").strip()

    cmd = f"""sudo adduser --disabled-password --gecos "" {username} && echo "{username}:{user_pw}" | sudo chpasswd"""
    stdin, stdout, stderr = cli.exec_command(cmd)
    err = stderr.read().decode("utf-8")

    if not err:
        print(f"[USER] home 디렉토리에 /home/{username} 폴더가 생성되었습니다. 유저 추가 완료!")
    else:
        print(f"[USER ERROR] 계정 생성 실패: {err}")


# ============================================================
# Ubuntu Samba / FTP
# ============================================================

def ubt_samba_mounting(cli, ip, smb_dir, mnt_path, username, passwd):
    cred_path = "/etc/samba/cred/"
    cred_file = cred_path + username

    cmd = "DEBIAN_FRONTEND=noninteractive apt -y install samba cifs-utils"
    stdin, stdout, stderr = cli.exec_command(cmd)
    output, error = cli_error_check(stdout, stderr)

    cmd = """mkdir -p %s
mkdir -p %s
cat > %s << EOF
username=%s
password=%s
EOF
chmod 700 %s
chmod 600 %s
""" % (cred_path, mnt_path, cred_file,
       username, passwd,
       cred_path, cred_file)

    stdin, stdout, stderr = cli.exec_command(cmd)
    output, error = cli_error_check(stdout, stderr)

    cmd = """grep -q '//%s/%s ' /etc/fstab || \
echo '//%s/%s %s cifs credentials=%s,iocharset=utf8,vers=3.0 0 0' >> /etc/fstab
systemctl daemon-reload
mount -a
""" % (ip, smb_dir,
       ip, smb_dir,
       mnt_path, cred_file)

    stdin, stdout, stderr = cli.exec_command(cmd)
    output, error = cli_error_check(stdout, stderr)


def ubt_restricted_ftp_setting(cli, user):
    cmd = """DEBIAN_FRONTEND=noninteractive apt -y install vsftpd &&
sed -i 's|^#*write_enable=.*|write_enable=YES|' /etc/vsftpd.conf &&
sed -i 's|^#*userlist_enable=.*|userlist_enable=NO|' /etc/vsftpd.conf &&
sudo sed -i 's/^auth.*required.*pam_shells.so/#&/' /etc/pam.d/vsftpd &&
usermod -s /usr/sbin/nologin %s &&
systemctl enable --now vsftpd &&
systemctl restart vsftpd
""" % user

    stdin, stdout, stderr = cli.exec_command(cmd)
    output, error = cli_error_check(stdout, stderr)


# ============================================================
# Ubuntu 메뉴
# ============================================================

def ubt_show_menu():
    res = int(input("""
    실행할 작업의 번호 선택하세요.
    1. 방화벽 해제
    2. 패키지 업데이트
    3. 패키지 세팅(wget, vim, libstdc++, tar, gzip)
    4. 미니콘다 설치
    5. 주피터 노트북 실행 설정
    6. systempython, 파라미코 설치
    7. dhcp ip 자동할당
    8. netplan ip 수동 변환 및 할당
    9. netplan 디렉토리 yaml 파일 리스트 갱신
    10. yaml 파일 내용 파일 생성
    11. ip a
    12. ip r
    13. 패키지 확인 및 설치
    14. http 웹 서비스 설치 및 설정
    0. 종료
    선택: """))
    return res


def ubt_run_cmd(cli, shell, cmd):
    firewall_meth = [
        "systemctl disable --now ufw",
        "systemctl status ufw",
        "init 6"
    ]

    package_update_meth = [
        "rm /var/lib/apt/lists/lock",
        "rm /var/cache/apt/archives/lock",
        "rm /var/lib/dpkg/lock*",
        "dpkg --configure -a",
        "apt update",
        "apt update && apt -y upgrade"
    ]

    package_setting_meth = [
        "apt upgrade",
        "apt -y install software-properties-common wget vim libstdc++6 tar gzip build-essential",
        "apt -y update && apt -y upgrade"
    ]

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
    ]

    jupyternotebook_meth = [
        "apt -y install expect",
        r"""expect -c 'spawn /root/miniconda3/bin/jupyter notebook password; expect "Enter password:"; send "asd123!@\r"; expect "Verify password:"; send "asd123!@\r"; expect eof'""",
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
        "systemctl daemon-reload",
        "systemctl enable jupyter.service",
        "systemctl restart jupyter.service",
        "systemctl status jupyter.service --no-pager",
        "ss -lntp | grep 8080"
    ]

    pythonsystem_paramiko_meth = [
        "/root/miniconda3/bin/conda install pip -y",
        "/root/miniconda3/bin/pip install --upgrade pip",
        "/root/miniconda3/bin/pip install paramiko",
        "/root/miniconda3/bin/conda install -y -c conda-forge types-cryptography",
        "/root/miniconda3/bin/python3 -m pip install ipykernel",
        "/root/miniconda3/bin/python3 -m ipykernel install --user --name system-python --display-name \"Python 3 (System)\""
    ]

    netplan_ls = ["ls /etc/netplan"]
    ub_ip_a = ["ip a"]
    ub_ip_r = ["ip r"]

    cmd_dict = {
        1: firewall_meth,
        2: package_update_meth,
        3: package_setting_meth,
        4: miniconda_meth,
        5: jupyternotebook_meth,
        6: pythonsystem_paramiko_meth,
        9: netplan_ls,
        11: ub_ip_a,
        12: ub_ip_r,
    }

    if cmd in [7, 8]:
        stdin, stdout, stderr = cli.exec_command(
            "ip -o link show | awk -F': ' '{print $2}' | grep -v '^lo$' | head -n1"
        )
        interface = stdout.read().decode("utf-8").strip()

        if interface == "":
            print("인터페이스 정보를 불러오지 못했습니다.")
            return

        print("선택된 인터페이스:", interface)

        stdin, stdout, stderr = cli.exec_command(
            "ls /etc/netplan | grep '.yaml$' | head -n1"
        )
        target_file = stdout.read().decode("utf-8").strip()

        if target_file == "":
            print("netplan yaml 파일을 찾지 못했습니다.")
            return

        print("선택된 netplan 파일:", target_file)

        if cmd == 7:
            new_yaml = ubt_create_dhcp_yaml(interface)
            print(interface + " 네트워크를 DHCP로 전환합니다.")
        else:
            new_yaml = ubt_create_static_yaml(interface)
            print(interface + " 네트워크를 정적 IP로 전환합니다.")

        sftp = cli.open_sftp()
        file = sftp.file("/tmp/netplan_auto.yaml", "w")
        file.write(new_yaml)
        file.close()
        sftp.close()

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

    if cmd == 13:
        ubt_package_check_install(cli)
        return

    if cmd == 14:
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

    if cmd == 9:
        ubt_netplan_list_meth(output)
    if cmd == 11:
        ubt_ip_a(output)
    if cmd == 12:
        ubt_ip_r(output)


def ubt_menu(device_info):
    cli = connect_linux(device_info)

    if cli is None:
        print("리눅스 연결 실패로 메뉴를 종료합니다.")
        return

    shell = cli.invoke_shell()
    time.sleep(1)

    while True:
        select = int(ubt_show_menu())

        if select not in range(0, 15):
            print("입력 범위를 벗어났습니다. 다시 입력해 주세요.")
            continue

        elif select == 0:
            print("exit")
            break

        else:
            ubt_run_cmd(cli, shell, select)

    cli.close()


# ============================================================
# 메인 실행
# ============================================================

def main():
    while True:
        select = input("[시작 메뉴]\n1.계정 생성\n2.장비 접속\n0.프로그램 종료\n 원하는 기능을 선택하세요 : ")
        if select not in ['1', '2', '0']:
            print("잘못된 입력입니다.")
            continue
        elif select == '0':
            print("프로그램을 종료합니다.")
            break
        elif select == '1':
            create_dev_info()
        elif select == '2':
            connect_dev()


main()
