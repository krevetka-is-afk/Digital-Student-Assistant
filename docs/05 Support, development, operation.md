# 5. Поддержка, развитие, эксплуатация

1. **Как будет происходить поддержка, сопровождение, обновления?** Каждый поддерживает свою зону ответсвенности + при необходимости приходит на помощь

2. **Планируем ли расширение функциональности / масштабирование в будущем?**
   1. Аналитика для ЦППРП
   2. ?Мобильный клиент?
   3. Устранение использованиея стронних форм (по типу яндекс форм)

3. **Какие качественные критерии успеха / метрики?** Соблюдение NFR и положительный фидбэк пользователей

## Эксплуатационная защита данных

- Production VM должна иметь ежедневный ночной backup PostgreSQL через
  `scripts/install-backup-timer.sh prod`.
- Backup по умолчанию запускается в `03:20`, пишет gzip-dump в
  `/var/backups/dsa/prod/<timestamp>/postgres.sql.gz` и хранит 14 дней.
- Для ручной проверки используется `DSA_ENVIRONMENT=prod scripts/backup-stack.sh`.
- Restore выполняется через
  `DSA_ENVIRONMENT=prod scripts/restore-postgres.sh /var/backups/dsa/prod/<timestamp>/postgres.sql.gz`.
- Neo4j Community не включен в автоматический online backup: live-архив volume
  может быть неконсистентным. Если graph-data станет production-critical, нужен
  отдельный maintenance-window dump/restore и регулярная проверка восстановления.
