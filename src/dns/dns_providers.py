# dns/dns_providers.py
"""
Список DNS провайдеров для UI
"""

DNS_PROVIDERS = {
    "Популярные": {
        "Cloudflare": {
            "ipv4": ["1.1.1.1", "1.0.0.1"],
            "ipv6": ["2606:4700:4700::1111", "2606:4700:4700::1001"],
            "desc": "Быстрый и приватный",
            "icon": "fa5s.bolt",
            "color": "#f48120",
            "doh": "https://cloudflare-dns.com/dns-query"
        },
        "Google DNS": {
            "ipv4": ["8.8.8.8", "8.8.4.4"],
            "ipv6": ["2001:4860:4860::8888", "2001:4860:4860::8844"],
            "desc": "Надёжный",
            "icon": "fa5b.google",
            "color": "#4285f4",
            "doh": "https://dns.google/dns-query"
        },
        "Dns.SB": {
            "ipv4": ["185.222.222.222", "45.11.45.11"],
            "ipv6": ["2a09::", "2a11::"],
            "desc": "Без цензуры",
            "icon": "fa5s.shield-alt",
            "color": "#00bcd4",
            "doh": "https://doh.sb/dns-query"
        },
    },
    "Безопасные": {
        "Quad9": {
            "ipv4": ["9.9.9.9", "149.112.112.112"],
            "ipv6": ["2620:fe::fe", "2620:fe::9"],
            "desc": "Антивирус",
            "icon": "fa5s.shield-virus",
            "color": "#e91e63",
            "doh": "https://dns.quad9.net/dns-query"
        },
        "AdGuard": {
            "ipv4": ["94.140.14.14", "94.140.15.15"],
            "ipv6": ["2a10:50c0::ad1:ff", "2a10:50c0::ad2:ff"],
            "desc": "Без рекламы",
            "icon": "fa5s.ad",
            "color": "#68bc71",
            "doh": "https://dns.adguard.com/dns-query"
        },
        "OpenDNS": {
            "ipv4": ["208.67.222.222", "208.67.220.220"],
            "ipv6": ["2620:119:35::35", "2620:119:53::53"],
            "desc": "Фильтрация",
            "icon": "fa5s.user-shield",
            "color": "#ff9800",
            "doh": "https://doh.opendns.com/dns-query"
        },
        "dnsdoh.art": {
            "ipv4": ["194.180.189.33", "194.180.189.33"],
            "ipv6": [],
            "desc": "Максимальная приватность",
            "icon": "fa5s.lock",
            "color": "#9c27b0",
            "doh": "https://dnsdoh.art:444/dns-query"
        }
    },
    "Для ИИ": {
        "Xbox DNS": {
            "ipv4": ["176.99.11.77", "80.78.247.254"],
            "ipv6": [],
            "desc": "ChatGPT",
            "icon": "fa5s.robot",
            "color": "#9c27b0"
        },
        "Comss DNS": {
            "ipv4": ["83.220.169.155", "212.109.195.93"],
            "ipv6": [],
            "desc": "ChatGPT",
            "icon": "fa5s.brain",
            "color": "#673ab7"
        },
        "dns.malw.link": {
            "ipv4": ["84.21.189.133", "64.188.98.242"],
            "ipv6": ["2a12:bec4:1460:d5::2", "2a01:ecc0:2c1:2::2"],
            "desc": "ChatGPT",
            "icon": "fa5s.comments",
            "color": "#2196f3",
            "doh": "https://dns.malw.link/dns-query"
        },
    }
}

