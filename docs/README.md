<h1 align="center"><img src="https://i.imgur.com/uABXHHI.png" width="30px"></img> <a href="https://github.com/bol-van/zapret">Zapret</a> (Запрет: обход блокировки Дискорда и Ютуба) </h1>

![image](https://github.com/user-attachments/assets/60ca6d7e-9e24-4829-80e7-2ddc570560a3)

- Возможность обхода блокировок Ютуба и Дискорда (через ядро `winws.exe`)
- Возможность разблокировать доступ к неработающим сайтом ChatGPT, Google Gemini, Notion и другим заблокированным для России ресурсам (через файл `hosts`)
- Возможность прописать кастомные DNS сервера (против атак провайдеров типа подмены ДНС)

> [!IMPORTANT]  
> Есть вопросы? Задай их здесь: https://github.com/youtubediscord/zapret/issues/new или же в группе https://t.me/youtubenotwork или https://discord.gg/kkcBDG2uws

> [!CAUTION]  
> Совсем никак не работает Запрет?
> 
> Попробуйте наш новый HTTP VPN на основе Tor с безлимитной скоростью: https://github.com/youtubediscord/roskomfree

## ❗ Хочу быстро и просто. Как установить и использовать? 
### Для новичков
**Для неопытных пользователей рекомендуем: https://t.me/bypassblock/399** ([зеркало](https://github.com/youtubediscord/zapret/releases/latest/download/ZapretSetup.exe))

### Собрать Zapret самостоятельно
https://github.com/youtubediscord/zapret/blob/main/docs/build.md

## 🗳️ О версиях
Наш GUI лаунчер имеет несколько основных версий (каналов обновления).

### Стабильные версии
Стабильные (релизные) сборки поставляются через лаунчер `ZapretSetup.exe`.

Обновления доступно из под программы по кнопке "Обновить" или по ссылке: https://t.me/bypassblock/399

### Dev версии (портабельная версия)
> [!CAUTION]  
> **Данные версии предназначены для ОПЫТНЫХ пользователей!**

Дев версии (сборки) являются тестовыми версиями, которые мгновенно позволяют протестировать новые фишки и опции до того как они попадут в стабильный канал релизов.

Список основных изменений:
- Обновления выходят в разы чаще и могут содержать непроверенные функции
- Во всех дев сборках отключены автообновления полностью 
- Все дев сборки поддерживают портабельный режим
- Усиленный сбор телеметрии
- Поддержка по ним не поддерживается (при любых ошибках используйте стабильные релизные сборки)

Обновления по ним доступны только через GitHub или Telegram канал по скачиваю нового `7z` архива.

### Консольные версии (без GUI, Win7)
Подробнее тут: https://github.com/youtubediscord/zapret/releases/tag/win7

## ❓ Часто задаваемые вопросы (FAQ)
### Сайт никак не хочет работать
> [!NOTE]  
> **Программа по умолчанию работает в режиме "Разблокируй все сайты, если не указано иное"**. Но при этом существует несколько способов принудительно добавить свои сайты. 

Нажмите на кнопку `Открыть Папку Zapret`, перейдите в папку `bin` найдите там файл `other.txt` и введите все интересующие Вас домены.

Чтобы исключить свои сайты из списка программы - есть специальные кнопки в меню.

Запрет не сможет разблокировать сайт если он заблокирован по айпи. Для этого следует использовать разблокировку через hosts.

Список доменов у которого нет второго (_других_) IP и следовательно не будут работать через Zapret:
- https://animego.org (если айпишник `185.178.208.138`, но на некоторых провайдерах этот IP пингуется!)
- https://mail.proton.me (если айпишник `3.66.189.153`, `3.73.85.131`, `185.70.42.37`)
- https://www.instagram.com (если айпишник `157.240.205.174`)
- https://static.cdninstagram.com (если айпишник `157.240.205.63`)

### У меня сломался Zapret после ваших обновлений
Ваша стратегия обхода перестала работать? Вероятно, дело в обновлении DPI у вашего провайдера.

Если ваш привычный способ обхода блокировок перестал работать или его эффективность заметно снизилась, поймите следующее:

*   **Сам "запрет" не "сломался" и не перестал действовать.** Механизмы блокировки остаются активными.
*   **Стратегии обхода, заложенные в нашей программе, как правило, стабильны** и почти не меняются от обновления к обновлению.

**Наиболее вероятная причина – ваш интернет-провайдер обновил свои системы ТСПУ DPI (Deep Packet Inspection).** Именно эти системы анализируют ваш трафик. После обновления DPI ваша ранее работавшая стратегия обхода могла стать "видимой" для провайдера и перестать быть эффективной.

#### Что делать?
Вам необходимо **найти новую стратегию обхода в настройках программы и продолжить экспериментировать**, пока не подберете рабочий вариант для текущих условий вашего провайдера.

Также Вы можете опробовать **[`Blockcheck`](https://github.com/youtubediscord/zapret/blob/main/docs/blockcheck.md)** (для автоматического подбора стратегий)

### YouTube никак не хочет работать (все стратегии перепробовал)
![image](https://github.com/user-attachments/assets/8f0cad33-96cf-4247-8df9-c61c920e94ec)

Для начала вам следует проверить свои расширения в браузере.

Окно выше окно рассылает **SaveFrom** или **Юбуст**, которое может **мешать** работе Zapret. ЭТО ОКНО **НИКАК НЕ СВЯЗАНО С YOUTUBE** И НЕ ДОЛЖНО ПОЯВЛЯТЬСЯ НА САЙТЕ!

**Отключайте расширения в браузерах перед тем как тестировать Zapret! (_не добавляйте в исключения расширения сайт Ютуба, а именно отключите!_)** Заместо SaveFrom.net рекомендуем использовать для скачивания видеороликов с Ютуба программу: https://github.com/yt-dlp/yt-dlp

Не используйте расширения:
- Savefrom
- Юбуст
- Adblock
- Антизапрет
- Adguard

### О Яндекс Браузере и Яндекс ДНС
> [!CAUTION]  
> [Яндекс DNS](https://t.me/bypassblock/134) перестали открывать Discord и другие заблокированные сайты. Не пользуйтесь ими. Рекомендуем сменить их на [**Google DNS**](https://developers.google.com/speed/public-dns) или [**Quad9 DNS**](https://quad9.net/service/service-addresses-and-features).

![image](https://github.com/user-attachments/assets/e8a11aa1-446c-40f4-b7d4-fc35b26ba9af)

Мы настоятельно **НЕ** рекомендуем использовать Яндекс Браузер! Он может нарушать работу Zapret. Например:
- Подменять днс (меняется в настройках)
- Просто блокировать ютуб через свои механизмы
- Устанавливать свои расширения, которые мешают работе Ютуба

### У меня не работает mitmproxy
Это известная проблема. Обе программы используют WinDivert. Отключите Zapret и mitmproxy будет работать вновь.

<h2 align="center">Хочу узнать подробнее </h2>

### [🛡 Что такое Zapret](https://teletype.in/@censorliber/zapretvpndpi)
### [Как работает Запрет](https://github.com/youtubediscord/zapret/blob/main/docs/flags.md)
### [👾 О вирусах](https://teletype.in/@censorliber/zapretvirus)

> [!CAUTION]  
> [Касперский](https://github.com/bol-van/zapret/issues/611) и иные российские вирусы начали войну с запретами и иными средствами обхода блокировок. Чтобы использовать их спокойно рекомендуется перейти на **альтернативные** антивирусы (Defender, ESET32 и т.д.), которые не выдают ложные и обманчивые срабатывания и помогают от большего количества угроз. Также не следует использовать российские антивирусы, либо добавлять файлы в исключения.

### Другие полезные сервисы и VPN https://github.com/awesome-windows11/CensorNet

> [!CAUTION]  
> При любых ошибках просьба **ВСЕГДА** оставляйте скриншот и изображение ошибки.
> 
> Не описывайте их на словах (ничего не работает, не запускается и т.д.), **так Вам нельзя будет помочь**, так как не понятно что за проблема.
>
> 
> Также следует писать Вашего **провайдера и город**, чтобы можно было составить список рабочих конфигураций для различных провайдеров, который будет не публичный.

> [!WARNING]  
> Если не работает Discord, указывается используете ли вы **приложение** или веб браузер. Если используется **веб браузер** (_что рекомендуется_), то указывайте бренд и имя версии.

> [!TIP]  
> Если совсем отчаетесь то можете написать в [ЛС **БЕСПЛАТНЫЙ** запрос на удалённую настройку](https://t.me/youtubenotwork/4764) через AnyDesk. В любой момент подключение можно завершить и удалить программу.

 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=youtubediscord/zapret&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=youtubediscord/zapret&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=youtubediscord/zapret&type=Date" />
 </picture>
