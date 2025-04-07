import paramiko
import sys
import os
from typing import List
from dotenv import load_dotenv


class PostgresInstaller:
    def __init__(self):
        self.ssh_clients = {}
        load_dotenv()
        self.db_password = os.getenv('POSTGRES_STUDENT_PASSWORD')
        if not self.db_password:
            sys.exit(1)

    def connect_ssh(self, host: str) -> bool:
        try:
            client = paramiko.SSHClient()
            client.load_system_host_keys()
            client.set_missing_host_key_policy(paramiko.RejectPolicy())
            client.connect(hostname=host, username='root', look_for_keys=True, timeout=10)
            self.ssh_clients[host] = client
            return True
        except:
            return False

    def get_os_type(self, host: str) -> str:
        stdin, stdout, _ = self.ssh_clients[host].exec_command(
            "grep -E '^ID=' /etc/os-release | cut -d= -f2 | tr -d '\"' | tr '[:upper:]' '[:lower:]'"
        )
        return stdout.read().decode().strip()

    def get_server_load(self, host: str) -> float:
        stdin, stdout, _ = self.ssh_clients[host].exec_command(
            "cat /proc/loadavg | awk '{print $1}'"
        )
        return float(stdout.read().decode().strip())

    def install_postgres(self, host: str, os_type: str) -> bool:
        if os_type == 'debian':
            cmds = [
                "apt-get update -y",
                "apt-get install -y postgresql postgresql-contrib",
                "systemctl start postgresql",
                "systemctl enable postgresql"
            ]
        else:
            cmds = [
                "dnf install -y postgresql-server postgresql-contrib",
                "postgresql-setup --initdb",
                "systemctl start postgresql",
                "systemctl enable postgresql",
                "firewall-cmd --add-service=postgresql --permanent",
                "firewall-cmd --reload"
            ]
        for cmd in cmds:
            if self.ssh_clients[host].exec_command(cmd)[1].channel.recv_exit_status() != 0:
                return False
        return True

    def setup_student_user(self, host: str) -> bool:
        cmds = [
            f"sudo -u postgres psql -c \"CREATE USER student WITH PASSWORD '{self.db_password}'\"",
            "sudo -u postgres createdb -O student student_db",
            "sudo -u postgres psql -c \"GRANT ALL PRIVILEGES ON DATABASE student_db TO student\""
        ]
        for cmd in cmds:
            if self.ssh_clients[host].exec_command(cmd)[1].channel.recv_exit_status() != 0:
                return False
        return True

    def configure_postgres(self, host: str, os_type: str, client_ip: str) -> bool:
        conf_dir = "/etc/postgresql/*/main" if os_type == 'debian' else "/var/lib/pgsql/data"
        cmds = [
            f"sed -i \"s/^#listen_addresses.*/listen_addresses = '*'/\" {conf_dir}/postgresql.conf",
            f"grep -q 'host all student {client_ip}/32 md5' {conf_dir}/pg_hba.conf || "
            f"echo 'host all student {client_ip}/32 md5' >> {conf_dir}/pg_hba.conf",
            "systemctl restart postgresql"
        ]
        for cmd in cmds:
            if self.ssh_clients[host].exec_command(cmd)[1].channel.recv_exit_status() != 0:
                return False
        return True

    def install_postgres_client(self, host: str) -> bool:
        _, stdout, _ = self.ssh_clients[host].exec_command("command -v psql")
        if stdout.channel.recv_exit_status() == 0:
            return True
        os_type = self.get_os_type(host)
        cmds = ["apt-get update -y", "apt-get install -y postgresql-client"] if os_type == 'debian' else ["dnf install -y postgresql"]
        for cmd in cmds:
            if self.ssh_clients[host].exec_command(cmd)[1].channel.recv_exit_status() != 0:
                return False
        return True

    def test_connection(self, target_host: str, client_host: str) -> bool:
        if not self.install_postgres_client(client_host):
            return False
        cmd = f"PGPASSWORD='{self.db_password}' psql -h {target_host} -U student -d student_db -c 'SELECT 1'"
        return self.ssh_clients[client_host].exec_command(cmd)[1].channel.recv_exit_status() == 0

    def install(self, hosts: List[str]) -> bool:
        try:
            print("Starting PostgreSQL installation")

            for host in hosts:
                print(f"Connecting to {host}...", end='', flush=True)
                if not self.connect_ssh(host):
                    print(" FAILED")
                    return False
                print(" OK")

            target_host = min(hosts, key=lambda h: self.get_server_load(h))
            client_host = next(h for h in hosts if h != target_host)
            os_type = self.get_os_type(target_host)

            print(f"Selected target host: {target_host}")
            print(f"Installing PostgreSQL on {target_host}...", end='', flush=True)
            if not self.install_postgres(target_host, os_type):
                print(" FAILED")
                return False
            print(" OK")

            print("Creating database user...", end='', flush=True)
            if not self.setup_student_user(target_host):
                print(" FAILED")
                return False
            print(" OK")

            print("Configuring PostgreSQL access...", end='', flush=True)
            if not self.configure_postgres(target_host, os_type, client_host):
                print(" FAILED")
                return False
            print(" OK")

            print("Verifying remote connection...", end='', flush=True)
            if not self.test_connection(target_host, client_host):
                print(" FAILED")
                return False
            print(" OK")

            print("PostgreSQL installation completed successfully")
            return True
        finally:
            for client in self.ssh_clients.values():
                client.close()



if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(1)
    hosts = sys.argv[1].split(',')
    if len(hosts) != 2:
        sys.exit(1)
    sys.exit(0 if PostgresInstaller().install(hosts) else 1)
