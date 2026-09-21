# meta developer: @Wers1xx
# meta pic: https://img.icons8.com/fluency/96/container.png
# meta banner: https://via.placeholder.com/1200x300.png?text=Container+Info

from .. import loader, utils
import subprocess
import logging
import asyncio
import os
import platform

logger = logging.getLogger(__name__)

@loader.tds
class ContainerInfoMod(loader.Module):
    """Модуль для просмотра информации о контейнере"""
    
    strings = {
        "name": "ContainerInfo",
        "no_info": "<emoji document_id=5352703271536454445>❌</emoji> <b>Не удалось получить информацию</b>",
        "loading": "<emoji document_id=5253464392850221514>🔃</emoji> <b>Собираю информацию о контейнере...</b>",
        "title": "<emoji document_id=5967456680940671207>🗃</emoji> <b>Информация о контейнере</b>\n\n",
        "memory_title": "<emoji document_id=5373342633798167891>💾</emoji> <b>Память:</b>\n",
        "cpu_title": "<emoji document_id=5260343246831237239>⚙️</emoji> <b>CPU:</b>\n",
        "disk_title": "<emoji document_id=6024086962904766974>💿</emoji> <b>Диск:</b>\n",
        "network_title": "<emoji document_id=5224455475063459688>🌐</emoji> <b>Сеть:</b>\n",
        "system_title": "<emoji document_id=5326045427437420393>💻</emoji> <b>Система:</b>\n",
        "docker_title": "<emoji document_id=5222292529533167322>🐋</emoji> <b>Docker:</b>\n",
        "cgroup_title": "<emoji document_id=5368334006146322724>📊</emoji> <b>Cgroups:</b>\n",
        "container_type_title": "<emoji document_id=5231012545799666522>🔍</emoji> <b>Тип контейнера:</b>\n",
    }

    
    async def client_ready(self, client, db):
        self.client = client
        self.db = db
    
    def _run_command(self, command, timeout=5):
        """Выполнить команду и вернуть результат"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.stdout.strip(), result.stderr.strip(), result.returncode
        except subprocess.TimeoutExpired:
            return "", "Timeout", -1
        except Exception as e:
            return "", str(e), -1
    
    def _safe_int(self, value):
        """Безопасное преобразование в int"""
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    
    def _format_bytes(self, bytes_value):
        """Форматирование байтов в читаемый вид"""
        if bytes_value is None:
            return "unknown"
        
        try:
            bytes_value = int(bytes_value)
            if bytes_value > 10**15:  # Очень большое значение = unlimited
                return "unlimited"
            
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if bytes_value < 1024.0:
                    return f"{bytes_value:.2f} {unit}"
                bytes_value /= 1024.0
        except:
            pass
        
        return "unknown"
    
    def _detect_container_type(self):
        """Определить тип контейнера"""
        detection_methods = []
        
        # Docker
        if os.path.exists("/.dockerenv"):
            detection_methods.append("Docker (файл .dockerenv)")
        
        # containerd
        if os.path.exists("/run/containerd/containerd.sock"):
            detection_methods.append("containerd (socket)")
        
        # Kubernetes
        if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount"):
            detection_methods.append("Kubernetes (service account)")
        
        # LXC
        if os.path.exists("/run/.containerenv"):
            detection_methods.append("LXC/LXD (containerenv)")
        
        # OpenVZ
        if os.path.exists("/proc/vz"):
            detection_methods.append("OpenVZ (/proc/vz)")
        
        if os.path.exists("/proc/user_beancounters"):
            detection_methods.append("OpenVZ (user_beancounters)")
        
        # Проверка через /proc/1/cgroup
        stdout, _, code = self._run_command("cat /proc/1/cgroup 2>/dev/null")
        if code == 0 and stdout:
            cgroup_lower = stdout.lower()
            if "docker" in cgroup_lower:
                detection_methods.append("Docker (cgroup)")
            if "containerd" in cgroup_lower:
                detection_methods.append("containerd (cgroup)")
            if "kubepods" in cgroup_lower:
                detection_methods.append("Kubernetes (cgroup)")
            if "lxc" in cgroup_lower:
                detection_methods.append("LXC (cgroup)")
            if "libpod" in cgroup_lower:
                detection_methods.append("Podman (cgroup)")
        
        # Проверка через systemd-detect-virt
        stdout, _, code = self._run_command("systemd-detect-virt 2>/dev/null")
        if code == 0 and stdout and stdout != "none":
            detection_methods.append(f"systemd-detect-virt: {stdout}")
        
        # Проверка окружения
        stdout, _, code = self._run_command("env | grep -i -E 'container|docker|k8s|kubernetes' | head -3")
        if code == 0 and stdout:
            for line in stdout.split('\n')[:3]:
                if '=' in line:
                    var_name = line.split('=')[0]
                    detection_methods.append(f"Environment: {var_name}")
        
        return detection_methods if detection_methods else ["Не определено (возможно VM или физический сервер)"]
    
    def _get_memory_info(self):
        """Получить информацию о памяти"""
        info = []
        
        # free -h
        stdout, stderr, code = self._run_command("free -h")
        if code == 0:
            lines = stdout.split('\n')
            for line in lines:
                if 'Mem:' in line:
                    parts = line.split()
                    if len(parts) >= 7:
                        info.append(f"├ Всего: <code>{parts[1]}</code>")
                        info.append(f"├ Использовано: <code>{parts[2]}</code>")
                        info.append(f"├ Свободно: <code>{parts[3]}</code>")
                        info.append(f"├ Кэш: <code>{parts[5]}</code>")
                        info.append(f"├ Доступно: <code>{parts[6]}</code>")
        
        # Попытка получить лимиты cgroup v2
        stdout, _, code = self._run_command("cat /sys/fs/cgroup/memory.max 2>/dev/null")
        if code == 0 and stdout:
            if stdout.strip() == "max":
                info.append(f"├ Лимит cgroup v2: <code>unlimited</code>")
            else:
                limit = self._safe_int(stdout)
                if limit is not None:
                    info.append(f"├ Лимит cgroup v2: <code>{self._format_bytes(limit)}</code>")
        
        # Текущее использование cgroup v2
        stdout, _, code = self._run_command("cat /sys/fs/cgroup/memory.current 2>/dev/null")
        if code == 0 and stdout:
            current = self._safe_int(stdout)
            if current is not None:
                info.append(f"├ Текущее cgroup v2: <code>{self._format_bytes(current)}</code>")
        
        # Попытка cgroup v1
        stdout, _, code = self._run_command("cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null")
        if code == 0 and stdout:
            limit = self._safe_int(stdout)
            if limit is not None:
                info.append(f"├ Лимит cgroup v1: <code>{self._format_bytes(limit)}</code>")
        
        # Текущее использование cgroup v1
        stdout, _, code = self._run_command("cat /sys/fs/cgroup/memory/memory.usage_in_bytes 2>/dev/null")
        if code == 0 and stdout:
            usage = self._safe_int(stdout)
            if usage is not None:
                info.append(f"├ Текущее cgroup v1: <code>{self._format_bytes(usage)}</code>")
        
        # Информация из /proc/meminfo
        stdout, _, code = self._run_command("cat /proc/meminfo | grep -E 'MemTotal|MemAvailable|SwapTotal'")
        if code == 0:
            for line in stdout.split('\n'):
                if 'MemTotal' in line:
                    try:
                        value = int(line.split()[1]) * 1024  # в байтах
                        info.append(f"└ /proc/meminfo: <code>{self._format_bytes(value)} total</code>")
                    except:
                        pass
        
        return info
    
    def _get_cpu_info(self):
        """Получить информацию о CPU"""
        info = []
        
        # Количество ядер
        stdout, _, code = self._run_command("nproc")
        if code == 0 and stdout:
            info.append(f"├ Ядер: <code>{stdout}</code>")
        
        # CPU info
        stdout, _, code = self._run_command("cat /proc/cpuinfo | grep 'model name' | head -1")
        if code == 0 and stdout:
            model = stdout.split(':')[1].strip()
            info.append(f"├ Модель: <code>{model}</code>")
        
        # Загрузка CPU
        stdout, _, code = self._run_command("top -bn1 | grep 'Cpu(s)'")
        if code == 0:
            parts = stdout.split(',')
            if len(parts) > 0:
                user = parts[0].split(':')[1].strip()
                info.append(f"├ Загрузка: <code>{user}</code>")
        
        # CPU лимит cgroup v2
        stdout, _, code = self._run_command("cat /sys/fs/cgroup/cpu.max 2>/dev/null")
        if code == 0 and stdout:
            parts = stdout.split()
            if len(parts) == 2:
                if parts[1] == 'max':
                    info.append(f"├ Лимит CPU v2: <code>unlimited</code>")
                else:
                    try:
                        quota = int(parts[0])
                        period = int(parts[1])
                        if period > 0:
                            cpu_limit = quota / period
                            info.append(f"├ Лимит CPU v2: <code>{cpu_limit:.2f} cores</code>")
                    except (ValueError, ZeroDivisionError):
                        pass
        
        # CPU лимит cgroup v1
        stdout, _, code = self._run_command("cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us 2>/dev/null")
        if code == 0 and stdout:
            quota = self._safe_int(stdout)
            if quota is not None and quota > 0:
                stdout2, _, code2 = self._run_command("cat /sys/fs/cgroup/cpu/cpu.cfs_period_us 2>/dev/null")
                if code2 == 0 and stdout2:
                    period = self._safe_int(stdout2)
                    if period is not None and period > 0:
                        cpu_limit = quota / period
                        info.append(f"└ Лимит CPU v1: <code>{cpu_limit:.2f} cores</code>")
        
        return info
    
    def _get_disk_info(self):
        """Получить информацию о диске"""
        info = []
        
        stdout, _, code = self._run_command("df -h /")
        if code == 0:
            lines = stdout.split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 6:
                    info.append(f"├ Всего: <code>{parts[1]}</code>")
                    info.append(f"├ Использовано: <code>{parts[2]}</code>")
                    info.append(f"├ Свободно: <code>{parts[3]}</code>")
                    info.append(f"└ Использование: <code>{parts[4]}</code>")
        
        return info
    
    def _get_network_info(self):
        """Получить информацию о сети"""
        info = []
        
        # Hostname
        stdout, _, code = self._run_command("hostname")
        if code == 0:
            info.append(f"├ Hostname: <code>{stdout}</code>")
        
        # IP адреса
        stdout, _, code = self._run_command("hostname -I 2>/dev/null || ip addr show | grep 'inet ' | grep -v 127.0.0.1")
        if code == 0 and stdout:
            ips = stdout.split()
            for ip in ips[:3]:  # Показать первые 3 IP
                if ip and ip != '127.0.0.1':
                    info.append(f"├ IP: <code>{ip}</code>")
        
        # DNS
        stdout, _, code = self._run_command("cat /etc/resolv.conf | grep nameserver")
        if code == 0 and stdout:
            dns_servers = stdout.split('\n')
            for dns in dns_servers[:2]:
                if dns:
                    dns_ip = dns.split(' ')[-1]
                    info.append(f"├ DNS: <code>{dns_ip}</code>")
        
        # Сетевые интерфейсы
        stdout, _, code = self._run_command("ip link show | grep '^[0-9]' | awk -F: '{print $2}'")
        if code == 0 and stdout:
            interfaces = stdout.split()
            info.append(f"└ Интерфейсы: <code>{', '.join(interfaces)}</code>")
        
        return info
    
    def _get_system_info(self):
        """Получить информацию о системе"""
        info = []
        
        # OS
        stdout, _, code = self._run_command("cat /etc/os-release | grep PRETTY_NAME")
        if code == 0 and stdout:
            os_name = stdout.split('=')[1].strip('"')
            info.append(f"├ OS: <code>{os_name}</code>")
        
        # Kernel
        stdout, _, code = self._run_command("uname -r")
        if code == 0:
            info.append(f"├ Kernel: <code>{stdout}</code>")
        
        # Architecture
        stdout, _, code = self._run_command("uname -m")
        if code == 0:
            info.append(f"├ Architecture: <code>{stdout}</code>")
        
        # Uptime
        stdout, _, code = self._run_command("uptime -p")
        if code == 0:
            info.append(f"└ Uptime: <code>{stdout}</code>")
        
        return info
    
    def _get_docker_info(self):
        """Получить информацию о Docker"""
        info = []
        
        # Проверка наличия docker
        stdout, _, code = self._run_command("which docker")
        if code == 0:
            info.append(f"├ Docker: <code>установлен</code>")
            
            # Версия docker
            stdout, _, code = self._run_command("docker --version")
            if code == 0:
                info.append(f"├ Версия: <code>{stdout}</code>")
            
            # Docker socket
            if os.path.exists("/var/run/docker.sock"):
                info.append(f"├ Socket: <code>доступен</code>")
            else:
                info.append(f"├ Socket: <code>недоступен</code>")
        else:
            info.append(f"├ Docker: <code>не установлен</code>")
        
        # Проверка наличия docker-compose
        stdout, _, code = self._run_command("which docker-compose")
        if code == 0:
            info.append(f"└ Docker-compose: <code>установлен</code>")
        else:
            info.append(f"└ Docker-compose: <code>не установлен</code>")
        
        return info
    
    def _get_cgroup_info(self):
        """Получить информацию о cgroups"""
        info = []
        
        # Версия cgroup
        stdout, _, code = self._run_command("stat -fc %T /sys/fs/cgroup/ 2>/dev/null")
        if code == 0:
            if "cgroup2" in stdout:
                info.append(f"├ Версия: <code>v2</code>")
            elif "tmpfs" in stdout:
                info.append(f"├ Версия: <code>v1</code>")
        
        # Текущий cgroup
        stdout, _, code = self._run_command("cat /proc/self/cgroup 2>/dev/null")
        if code == 0 and stdout:
            info.append(f"├ Текущий: <code>{stdout}</code>")
        
        # Доступные контроллеры
        stdout, _, code = self._run_command("cat /sys/fs/cgroup/cgroup.controllers 2>/dev/null")
        if code == 0 and stdout:
            info.append(f"└ Контроллеры: <code>{stdout}</code>")
        
        return info
    
    @loader.command(
        ru="Информация о контейнере",
        en="Container information",
        emoji="📦"
    )
    async def cinfo(self, message):
        """Показать детальную информацию о контейнере"""
        await utils.answer(message, self.strings("loading"))
        
        # Определяем тип контейнера
        container_types = self._detect_container_type()
        
        result = self.strings("title")
        
        # Тип контейнера
        result += self.strings("container_type_title")
        result += "\n".join([f"├ <code>{ct}</code>" for ct in container_types])
        result += "\n\n"
        
        # Системная информация
        result += self.strings("system_title")
        system_info = self._get_system_info()
        if system_info:
            result += "\n".join(system_info) + "\n\n"
        else:
            result += self.strings("no_info") + "\n\n"
        
        # Память
        result += self.strings("memory_title")
        memory_info = self._get_memory_info()
        if memory_info:
            result += "\n".join(memory_info) + "\n\n"
        else:
            result += self.strings("no_info") + "\n\n"
        
        # CPU
        result += self.strings("cpu_title")
        cpu_info = self._get_cpu_info()
        if cpu_info:
            result += "\n".join(cpu_info) + "\n\n"
        else:
            result += self.strings("no_info") + "\n\n"
        
        # Диск
        result += self.strings("disk_title")
        disk_info = self._get_disk_info()
        if disk_info:
            result += "\n".join(disk_info) + "\n\n"
        else:
            result += self.strings("no_info") + "\n\n"
        
        # Сеть
        result += self.strings("network_title")
        network_info = self._get_network_info()
        if network_info:
            result += "\n".join(network_info) + "\n\n"
        else:
            result += self.strings("no_info") + "\n\n"
        
        # Docker
        result += self.strings("docker_title")
        docker_info = self._get_docker_info()
        if docker_info:
            result += "\n".join(docker_info) + "\n\n"
        else:
            result += self.strings("no_info") + "\n\n"
        
        # Cgroups
        result += self.strings("cgroup_title")
        cgroup_info = self._get_cgroup_info()
        if cgroup_info:
            result += "\n".join(cgroup_info)
        else:
            result += self.strings("no_info")
        
        await utils.answer(message, result)
    
    @loader.command(
        ru="Проверить контейнер",
        en="Check container",
        emoji="🔍"
    )
    async def ccon(self, message):
        """Проверить, запущено ли в контейнере"""
        container_types = self._detect_container_type()
        
        if len(container_types) > 0 and container_types[0] != "Не определено (возможно VM или физический сервер)":
            result = "✅ <b>Обнаружен контейнер:</b>\n\n"
            for ct in container_types:
                result += f"├ <code>{ct}</code>\n"
            await utils.answer(message, result)
        else:
            await utils.answer(message, "❌ <b>Контейнер не обнаружен</b>\n\nВозможно, это VM или физический сервер")