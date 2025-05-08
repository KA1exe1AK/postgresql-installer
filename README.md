# PostgreSQL Installer

Консольное приложение для автоматизированной установки и настройки PostgreSQL на одном из двух удалённых серверов (Debian или AlmaLinux). Подходит для выполнения в продакшене или CI/CD.

## Что делает

- Подключается к двум серверам по SSH
- Сравнивает нагрузку на них
- Устанавливает PostgreSQL на менее загруженном
- Создаёт пользователя `student` с паролем из `.env`
- Настраивает удалённый доступ только с IP второго сервера
- Проверяет подключение SQL-запросом `SELECT 1`

## Требования

- На обоих серверах доступен root с одним и тем же SSH-ключом
- Закрытая часть ключа установлена локально
- Установлен `paramiko`, `python-dotenv`:
  ```bash
  pip install paramiko python-dotenv
  ```

- Файл `.env` в каталоге с проектом:
  ```
  POSTGRES_STUDENT_PASSWORD=your_secure_password
  ```

## Запуск

```bash
python installer.py 192.168.1.10,192.168.1.11
```

Пример вывода:
```
Starting PostgreSQL installation
Connecting to 192.168.1.10... OK
Connecting to 192.168.1.11... OK
Selected target host: 192.168.1.10
Installing PostgreSQL on 192.168.1.10... OK
Creating database user... OK
Configuring PostgreSQL access... OK
Verifying remote connection... OK
PostgreSQL installation completed successfully
```

## Принятые решения

1. **Определение ОС** — через `/etc/os-release`, так как кросс-дистрибутивно.
2. **Проверка загрузки** — через `/proc/loadavg`, это быстрее и без лишних утилит.
3. **Firewall** — на CentOS открывается `postgresql`-сервис через `firewall-cmd`. На Debian — не требуется.
4. **SSH-хосты** — загружаются из системного `known_hosts`, без подстановок по ключу — безопаснее.
5. **Логика завершения** — `sys.exit(0)` при успехе, `1` при ошибках. Можно использовать в автоматизированных пайплайнах.

## 📂 Структура проекта

```
.
├── installer.py        
├── .env                
├── README.md          
```
