# Rocky http, dns 통합코드
# zones 에 팀 zone 등록, 팀 zone 생성, 반복[사용자 없으면 등록 -> VH 생성 -> index.html 생성 -> zone A 레코드에 등록] (중복체크)
# 설치 : roc_http_dns_install(cli)
# 실행 : roc_web_dns_set(cli)





def ubt_restricted_ftp_setting(cli, user):
    cmd = """DEBIAN_FRONTEND=noninteractive apt -y install vsftpd&&
sed -i 's|^#*write_enable=.*|write_enable=YES|' /etc/vsftpd.conf&&
sed -i 's|^#*userlist_enable=.*|userlist_enable=NO|' /etc/vsftpd.conf&&
sudo sed -i 's/^auth.*required.*pam_shells.so/#&/' /etc/pam.d/vsftpd&&
usermod -s /usr/sbin/nologin %s&&
systemctl enable --now vsftpd&&
systemctl restart vsftpd
"""%(user)

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

def roc_path_check(cli, file):
    cmd = "[ -e '%s' ] && echo 'y' || echo 'n'"%(file)
    stdin, stdout, stderr = cli.exec_command(cmd)
    output = stdout.read().decode('utf-8').strip()
    if output == 'y' :
        print("%s 가 존재합니다."%(file))
        return True
    else :
        print("%s 가 존재하지 않습니다."%(file))
        return False

def roc_user_add(cli, username=""):
    if username == "" :
        username = input("생성할 username 을 입력하세요 :")
    passwd = input("생성할 passwd를 입력하세요:")
    cmd = [
        "id '%s' >/dev/null 2>&1 || useradd -m '%s'" % (username, username),
        "echo '%s:%s' | chpasswd" % (username, passwd),
        "chmod 755 /home/%s"%(username),

    ]
    roc_run_command(cli, cmd)    

def roc_index_html_create(cli, user) :
    cmd = """chmod 755 /home/%s
cat << 'EOF' > /home/%s/index.html
created.
EOF
chmod 755 /home/%s/index.html
chown %s:%s /home/%s/index.html
ls -l /home/%s/index.html
""" % (user, user, user, user, user, user, user)
    
    stdin, stdout, stderr = cli.exec_command(cmd)
    cli_error_check(stdout,stderr)
    print("index.html 생성 완료.")

def roc_dns_allow(cli) :
    cmd= """sed -i 's/^[[:space:]]*listen-on port.*/        listen-on port 53 { any; };/' /etc/named.conf &&
sed -i 's/^[[:space:]]*allow-query.*/        allow-query     { any; };/' /etc/named.conf """
    
    stdin, stdout, stderr = cli.exec_command(cmd)
    cli_error_check(stdout,stderr)
    print("/etc/named.conf port, query allow any 설정 완료.")
    return

def roc_zone_add(cli,teamname,types) :
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
"""%(teamname,teamname,types,teamname)

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

def roc_httpd_healthcheck(cli) :
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

    roc_run_command(cli,[
    "named-checkconf",
    "named-checkzone %s.com /var/named/%s.com.zone" % (teamname,teamname),
    "systemctl restart named"
    ])
 
        
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
    

    
