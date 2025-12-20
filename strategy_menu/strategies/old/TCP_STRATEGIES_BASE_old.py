"""
Базовые TCP техники обхода DPI.
Только DPI-аргументы! Фильтры берутся из CATEGORIES_REGISTRY.base_filter
"""

from ..constants import LABEL_RECOMMENDED, LABEL_GAME, LABEL_CAUTION, LABEL_EXPERIMENTAL, LABEL_STABLE

TCP_STRATEGIES_BASE = {
    "none": {
        "name": "⛔ Отключено",
        "description": "Обход отключен",
        "args": ""
    },
    "other_seqovl": {
        "name": "YTDisBystro 3.4 v1 (all ports)",
        "description": "Раньше эта стратегия била по всем портам и отлично подходила для игр",
        "author": "hz",
        "label": LABEL_RECOMMENDED,
        "args": f"""--dpi-desync=multisplit --dpi-desync-split-seqovl=211 --dpi-desync-split-seqovl-pattern=tls_clienthello_5.bin"""
    },
    "multisplit_sniext_midsld_18": {
        "name": "multisplit sniext+1 midsld-1",
        "description": "Потом опишу позже",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=multisplit --dpi-desync-split-pos=sniext+1,midsld  --dpi-desync-split-seqovl=652"""
    },
    "dis4": {
        "name": "general (alt v2) 1.6.1 / 1.8.2",
        "description": "Устаревший split2 с seqovl 652 и паттерном 4",
        "author": "hz",
        "label": LABEL_RECOMMENDED,
        "args": f"""--dpi-desync=split2 --dpi-desync-split-seqovl=652 --dpi-desync-split-pos=2 --dpi-desync-split-seqovl-pattern=tls_clienthello_www_google_com.bin"""
    },
    "multisplit_fake_tls_badseq": {
        "name": "YTDisBystro 3.4 v1",
        "description": "Хорошая базовая комлектация для старта",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,multisplit --dpi-desync-split-pos=sld+1 --dpi-desync-fake-tls=0x0F0F0E0F --dpi-desync-fake-tls=tls_clienthello_14.bin --dpi-desync-fake-tls-mod=rnd,dupsid --dpi-desync-fooling=badseq --dpi-desync-autottl --dup=2 --dup-fooling=badseq --dup-autottl --dup-cutoff=n3"""
    },
    "multisplit_fake_tls_md5sig": {
        "name": "YTDisBystro 3.4 v3",
        "description": "Хорошая базовая комлектация для старта",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,multisplit --dpi-desync-split-pos=sld+1 --dpi-desync-fake-tls=0x0F0F0E0F --dpi-desync-fake-tls=tls_clienthello_14.bin --dpi-desync-fake-tls-mod=rnd,dupsid --dpi-desync-fooling=md5sig --dpi-desync-autottl --dup=2 --dup-fooling=md5sig --dup-autottl --dup-cutoff=n3"""
    },
    "dronatar_4_2": {
        "name": "Dronatar 4.2",
        "description": "fake fake-tls=0x00, repeats=6 badseq increment=0",
        "author": "Dronatar",
        "label": LABEL_RECOMMENDED,
        "args": f"""--dpi-desync=fake --dpi-desync-fake-tls-mod=rnd,dupsid --dpi-desync-repeats=6 --dpi-desync-fooling=badseq --dpi-desync-badseq-increment=0"""
    },
    "multidisorder_badseq_pos": {
        "name": "original bol-van v2 (badsum)",
        "description": "Дисордер стратегия с фуллингом badseq нарезкой и повтором 6",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,multidisorder --dpi-desync-split-pos=1,midsld --dpi-desync-repeats=6 --dpi-desync-fooling=badseq"""
    },
    "multidisorder_md5sig_pos": {
        "name": "original bol-van v2",
        "description": "Дисордер стратегия с фуллингом md5sig нарезкой и повтором 6",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,multidisorder --dpi-desync-split-pos=1,midsld --dpi-desync-repeats=6 --dpi-desync-fooling=badseq,md5sig"""
    },
    "multidisorder_ipset_syndata": {
        "name": "Ulta v2 / 06.01.2025",
        "description": "Использует адреса дискорда, вместо доменов",
        "author": "hz",
        "label": LABEL_RECOMMENDED,
        "args": f"""--dpi-desync=syndata --dpi-desync-fake-syndata=tls_clienthello_3.bin --dpi-desync-autottl"""
    },
    "original_bolvan_v2_badsum": {
        "name": "Если стратегия не работает смени её!",
        "description": "Потом опишу подробнее",
        "author": "hz",
        "label": LABEL_RECOMMENDED,
        "args": f"""--dpi-desync=fake,multidisorder --dpi-desync-split-pos=1,midsld --dpi-desync-repeats=6 --dpi-desync-fooling=badseq --dpi-desync-fake-tls-mod=rnd,dupsid,sni=www.google.com"""
    },
    "original_bolvan_v2_badsum_max": {
        "name": "Мессенджер Max",
        "description": "Потом опишу подробнее",
        "author": "hz",
        "label": LABEL_RECOMMENDED,
        "args": f"""--dpi-desync=fake,multidisorder --dpi-desync-split-pos=1,midsld --dpi-desync-repeats=6 --dpi-desync-fooling=badseq --dpi-desync-fake-tls-mod=rnd,dupsid,sni=web.max.ru"""
    },
    "multisplit_286_pattern": {
        "name": "YTDisBystro 3.4 v2 (1)",
        "description": "Дисордер стратегия с фуллингом badseq нарезкой и повтором 11",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=multisplit --dpi-desync-split-seqovl=286 --dpi-desync-split-seqovl-pattern=tls_clienthello_11.bin --dup=2 --dup-cutoff=n3"""
    },
    "multidisorder_super_split_md5sig": {
        "name": "Discord Voice & YT (badseq)",
        "description": "Обратная стратегия с нестандартной нарезкой и md5sig",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,multidisorder --dpi-desync-split-pos=method+2,midsld,5 --dpi-desync-ttl=0 --dpi-desync-fooling=md5sig,badsum,badseq --dpi-desync-repeats=15 --dpi-desync-fake-tls=tls_clienthello_www_google_com.bin"""
    },
    "multidisorder_super_split_badseq": {
        "name": "Discord Voice & YT (md5sig и badseq)",
        "description": "Обратная стратегия с нестандартной нарезкой и badseq",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,multidisorder --dpi-desync-split-pos=method+2,midsld,5 --dpi-desync-ttl=0 --dpi-desync-fooling=badsum,badseq --dpi-desync-repeats=15 --dpi-desync-fake-tls=tls_clienthello_www_google_com.bin"""
    },
    "multidisorder_w3": {
        "name": "Discord Voice & YT (DTLS)",
        "description": "Обратная стратегия с фейком tls w3 и md5sig",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,multidisorder --dpi-desync-fake-tls=dtls_clienthello_w3_org.bin --dpi-desync-split-pos=1,midsld --dpi-desync-fooling=badseq,md5sig"""
    },
    "multidisorder_pos_100": {
        "name": "Split Position",
        "description": "Обратная стратегия с нестандартной нарезкой и фейком TLS",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,multidisorder --dpi-desync-fake-tls-mod=rnd,dupsid --dpi-desync-repeats=3 --dpi-desync-split-pos=100,midsld,sniext+1,endhost-2,-10 --dpi-desync-ttl=4"""
    },
    "dis14": {
        "name": "multisplit и seqovl",
        "description": "Мульти нарезка с seqovl и нестандартной позицией",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=multisplit --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=midsld+1"""
    },
    "multisplit_3": {
        "name": "YTDisBystro 2.9.2 v1 / v2",
        "description": "Отлично подходит для YouTube",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=multisplit --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=midsld+1 --dpi-desync-split-seqovl-pattern=tls_clienthello_7.bin"""
    },
    "fake_badseq_rnd": {
        "name": "YTDisBystro 2.9.2 v1 (1)",
        "description": "Базовая стратегия десинхронизации с фейком tls rnd",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake --dpi-desync-fooling=badseq --dpi-desync-fake-tls=tls_clienthello_7.bin --dpi-desync-fake-tls-mod=rnd"""
    },
    "fakedsplit_badseq_4": {
        "name": "Фейк с фуулингом badseq и фейком tls 4",
        "description": "Десинхронизация badseq с фейком tls 4",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fakedsplit --dpi-desync-split-pos=midsld-1,1 --dpi-desync-fooling=badseq --dpi-desync-fakedsplit-pattern=tls_clienthello_4.bin --dpi-desync-autottl"""
    },
    "fake_autottl_faketls": {
        "name": "Фейк с авто ttl и фейком tls",
        "description": "Фейк с авто ttl и фейком tls (использовать с осторожностью)",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake --dpi-desync-ttl=1 --dpi-desync-autottl=4 --dpi-desync-fake-tls-mod=rnd,rndsni,padencap"""
    },
    "fake_datanoack_fake_tls": {
        "name": "Фейк с datanoack и фейком tls",
        "description": "Фейк с datanoack и фейком tls",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake --dpi-desync-fooling=datanoack --dpi-desync-fake-tls-mod=rnd,rndsni,padencap"""
    },
    "dis1": {
        "name": "Фейк с datanoack и padencap",
        "description": "Улучшенная стратегия с datanoack и padencap",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,fakeddisorder --dpi-desync-fooling=datanoack --dpi-desync-split-pos=midsld --dpi-desync-fake-tls-mod=rnd,rndsni,padencap"""
    },
    "dis2": {
        "name": "multisplit split pos padencap",
        "description": "Стандартный мультисплит с нарезкой и фейком padencap",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,multisplit --dpi-desync-ttl=1 --dpi-desync-split-pos=1,midsld --dpi-desync-fake-tls-mod=rnd,rndsni,padencap"""
    },
    "dis3": {
        "name": "split badseq 10",
        "description": "Стандартный сплит с фуллингом badseq и 10 повторами",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=split --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-ttl=4"""
    },
    "dis5": {
        "name": "fake split 6 google",
        "description": "Фейковый сплит с повторением 6 и фейком google",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,split --dpi-desync-repeats=6 --dpi-desync-fooling=badseq --dpi-desync-fake-tls=tls_clienthello_www_google_com.bin"""
    },
    "dis5": {
        "name": "fake split2 6 sberbank",
        "description": "Фейковый сплит2 с повторением 6 и фейком от сбербанка много деняк",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,split2 --dpi-desync-ttl=1 --dpi-desync-autottl=5 --dpi-desync-repeats=6 --dpi-desync-fake-tls=tls_clienthello_sberbank_ru.bin"""
    },
    "dis6": {
        "name": "syndata (на все домены!)",
        "description": "Стратегия работает на все домены и может ломать сайты (на свой страх и риск)",
        "author": "hz",
        "label": LABEL_CAUTION,
        "args": f"""--dpi-desync=syndata --dpi-desync-fake-syndata=tls_clienthello_3.bin --dpi-desync-ttl=5"""
    },
    "dis7": {
        "name": "Ростелеком & Мегафон",
        "description": "Сплит с повторением 6 и фуллингом badseq и фейком tls от Google",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,split --dpi-desync-autottl=2 --dpi-desync-repeats=6 --dpi-desync-fooling=badseq --dpi-desync-fake-tls=tls_clienthello_www_google_com.bin"""
    },
    "dis8": {
        "name": "Ростелеком & Мегафон v2",
        "description": "Cплит2 с фейком tls 4 и ttl 4 (короче одни четвёрки)",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,split2 --dpi-desync-split-seqovl=1 --dpi-desync-split-tls=sniext --dpi-desync-fake-tls=tls_clienthello_4.bin --dpi-desync-ttl=4"""
    },
    "dis9": {
        "name": "split2 sniext google",
        "description": "Cплит2 с фейком tls от Google",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,split2 --dpi-desync-split-seqovl=1 --dpi-desync-split-tls=sniext --dpi-desync-fake-tls=tls_clienthello_www_google_com.bin --dpi-desync-ttl=2"""
    },
    "dis10": {
        "name": "disorder2 badseq tls google",
        "description": "Cплит2 badseq с фейком tls от Google",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=syndata,disorder2 --dpi-desync-split-pos=3 --dpi-desync-repeats=11 --dpi-desync-fooling=badseq --dpi-desync-fake-tls=tls_clienthello_www_google_com.bin"""
    },
    "dis11": {
        "name": "split badseq 10",
        "description": "Cплит2 с фуллингом badseq и 10 повторами",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=split --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-autottl"""
    },
    "split_pos_badseq": {
        "name": "Ростелеком & Мегафон",
        "description": "Базовый split и badseq",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=split --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-autottl=2"""
    },
    "dis12": {
        "name": "split badseq 10 ttl",
        "description": "Cплит2 с фуллингом badseq и 10 повторами и ttl 3",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=split --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-ttl=3"""
    },
    "dis13": {
        "name": "fakedsplit badsrq 10",
        "description": "Фейки и сплиты с фуллингом badseq и 10 повторами",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fakedsplit --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-autottl"""
    },
    "alt1_161": {
        "name": "general (alt v1) 1.8.2",
        "description": "fake,split autottl 5 repeats 6 badseq и fake tls google",
        "author": "Flowseal",
        "label": None,
        "args": f"""--dpi-desync=fake,split --dpi-desync-autottl=5 --dpi-desync-repeats=6 --dpi-desync-fooling=badseq --dpi-desync-fake-tls=tls_clienthello_www_google_com.bin"""
    },
    "general_alt183": {
        "name": "general (alt) 1.8.3 / 1.8.4",
        "description": "Потом опишу подробнее",
        "author": "Flowseal",
        "label": None,
        "args": f"""--dpi-desync=fake,fakedsplit --dpi-desync-autottl=5 --dpi-desync-repeats=6 --dpi-desync-fooling=badseq --dpi-desync-fake-tls=tls_clienthello_www_google_com.bin"""
    },
    "general_alt185": {
        "name": "general (alt) 1.8.5",
        "description": "Потом опишу подробнее",
        "author": "Flowseal",
        "label": None,
        "args": f"""--dpi-desync=fake,fakedsplit --dpi-desync-repeats=6 --dpi-desync-fooling=ts --dpi-desync-fakedsplit-pattern=0x00 --dpi-desync-fake-tls=tls_clienthello_www_google_com.bin"""
    },
    "general_alt2183": {
        "name": "general (alt2) 1.8.3 / 1.8.4",
        "description": "Потом опишу подробнее",
        "author": "Flowseal",
        "label": None,
        "args": f"""--dpi-desync=multisplit --dpi-desync-split-seqovl=652 --dpi-desync-split-pos=2 --dpi-desync-split-seqovl-pattern=tls_clienthello_www_google_com.bin"""
    },
    "general_alt3183_2": {
        "name": "general (alt v3) 1.8.2 / 1.8.4",
        "description": "fakedsplit pos 1 autottl badseq repeats 8",
        "author": "Flowseal",
        "label": None,
        "args": f"""--dpi-desync=fakedsplit --dpi-desync-split-pos=1 --dpi-desync-autottl --dpi-desync-fooling=badseq --dpi-desync-repeats=8"""
    },
    "general_alt4_182": {
        "name": "general (alt v4) 1.8.2 / 1.8.4",
        "description": "Для Rockstar Launcher & Epic Games",
        "author": "https://github.com/Flowseal/zapret-discord-youtube/issues/2361",
        "label": None,
        "args": f"""--dpi-desync=fake,multisplit --dpi-desync-repeats=6 --dpi-desync-fooling=md5sig --dpi-desync-fake-tls=tls_clienthello_www_google_com.bin"""
    },
    "general_bf_2": {
        "name": "general (BF) 2.0",
        "description": "Для Battlefield 6",
        "author": "Flowseal",
        "label": LABEL_GAME,
        "args": f""" --dpi-desync=fake --dpi-desync-repeats=6 --dpi-desync-fake-tls-mod=none --dpi-desync-fooling=badseq"""
    },
    "general_alt5_182": {
        "name": "general (alt v5) 1.8.2 / 1.8.4",
        "description": "syndata",
        "author": "Flowseal",
        "label": LABEL_CAUTION,
        "args": f"""--ipcache-hostname --dpi-desync=syndata"""
    },
     "general_alt6_182": {
        "name": "general (alt v6) 1.8.2",
        "description": "multisplit repeats 2 seqovl 681 pos 1 badseq hopbyhop2",
        "author": "Flowseal",
        "label": None,
        "args": f"""--dpi-desync=multisplit --dpi-desync-repeats=2 --dpi-desync-split-seqovl=681 --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq,hopbyhop2 --dpi-desync-split-seqovl-pattern=tls_clienthello_www_google_com.bin"""
    },
    "general_alt6_184": {
        "name": "general (alt v6) 1.8.4",
        "description": "multisplit seqovl 681 pos 1 seqovl pattern",
        "author": "Flowseal",
        "label": None,
        "args": f"""--dpi-desync=multisplit --dpi-desync-split-seqovl=681 --dpi-desync-split-pos=1 --dpi-desync-split-seqovl-pattern=tls_clienthello_www_google_com.bin"""
    },
    "general_alt7_184": {
        "name": "general (alt v7) 1.8.4",
        "description": "multisplit seqovl 681 pos 1 seqovl pattern",
        "author": "Flowseal",
        "label": None,
        "args": f"""--dpi-desync=multisplit --dpi-desync-split-pos=2,sniext+1 --dpi-desync-split-seqovl=679 --dpi-desync-split-seqovl-pattern=tls_clienthello_www_google_com.bin"""
    },
    "general_alt8_185": {
        "name": "general (alt v8) 1.8.5",
        "description": "fake autottl repeats 6 badseq increment 2",
        "author": "V3nilla",
        "label": None,
        "args": f"""--dpi-desync=fake --dpi-desync-fake-tls-mod=none --dpi-desync-repeats=6 --dpi-desync-fooling=badseq --dpi-desync-badseq-increment=2"""
    },
    "general_alt8_185_2": {
        "name": "general (alt v8) 1.8.5 (2)",
        "description": "fake autottl repeats 6 badseq increment 0",
        "author": "V3nilla",
        "label": None,
        "args": f"""--dpi-desync=fake --dpi-desync-fake-tls-mod=none --dpi-desync-repeats=6 --dpi-desync-fooling=badseq --dpi-desync-badseq-increment=0"""
    },
    "general_alt8_185_3": {
        "name": "general (alt v8) 1.8.5 (3)",
        "description": "fake autottl repeats 6 badseq increment 100000",
        "author": "V3nilla",
        "label": None,
        "args": f"""--dpi-desync=fake --dpi-desync-fake-tls-mod=none --dpi-desync-repeats=6 --dpi-desync-fooling=badseq --dpi-desync-badseq-increment=100000"""
    },
    "fake_autottl_repeats_6_badseq": {
        "name": "alt mgts (v1) 1.6.1 / 1.8.4",
        "description": "fake autottl repeats 6 badseq",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake --dpi-desync-autottl=2 --dpi-desync-repeats=6 --dpi-desync-fooling=badseq --dpi-desync-fake-tls=tls_clienthello_www_google_com.bin"""
    },
    "general_simplefake_185": {
        "name": "general simple fake alt 1.8.5",
        "description": "fake autottl repeats 6 badseq",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake --dpi-desync-repeats=6 --dpi-desync-fooling=badseq --dpi-desync-badseq-increment=10000000 --dpi-desync-fake-tls=tls_clienthello_www_google_com.bin"""
    },
    "altmgts2_161_2": {
        "name": "alt mgts (v2) 1.6.1 / 1.8.4",
        "description": "fake autottl repeats 6 md5sig",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake --dpi-desync-repeats=6 --dpi-desync-fooling=md5sig --dpi-desync-fake-tls=tls_clienthello_www_google_com.bin"""
    },
    "general_simple_fake_165_2": {
        "name": "general simple fake 1.8.5 v2",
        "description": "fake autottl repeats 6 ts",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake --dpi-desync-repeats=6 --dpi-desync-fooling=ts --dpi-desync-fake-tls=tls_clienthello_www_google_com.bin"""
    },
    "altmgts2_161_3": {
        "name": "alt mgts (v3) 1.6.1",
        "description": "fake autottl repeats 6 md5sig",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake --dpi-desync-autottl=2 --dpi-desync-repeats=6 --dpi-desync-fooling=md5sig --dpi-desync-fake-tls=tls_clienthello_www_google_com.bin"""
    },
    "general_fake_tls_auto_alt_184": {
        "name": "general (fake TLS auto alt) 1.8.4",
        "description": "multisplit seqovl 681 pos 1 seqovl pattern",
        "author": "Flowseal",
        "label": None,
        "args": f"""--dpi-desync=fake,fakedsplit --dpi-desync-split-pos=1 --dpi-desync-autottl --dpi-desync-fooling=badseq --dpi-desync-badseq-increment=10000000 --dpi-desync-repeats=8 --dpi-desync-fake-tls-mod=rnd,dupsid,sni=www.google.com"""
    },
    "general_fake_tls_auto_alt_185": {
        "name": "general (fake TLS auto alt) 1.8.5",
        "description": "multisplit seqovl 681 pos 1 seqovl pattern",
        "author": "Flowseal",
        "label": None,
        "args": f"""--dpi-desync=fake,fakedsplit --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-badseq-increment=10000000 --dpi-desync-repeats=8 --dpi-desync-fake-tls-mod=rnd,dupsid,sni=www.google.com"""
    },
    "general_fake_tls_auto_alt3_184": {
        "name": "general (fake TLS auto alt3) 1.8.4",
        "description": "multisplit seqovl 681 pos 1 seqovl pattern",
        "author": "Flowseal",
        "label": None,
        "args": f"""--dpi-desync=fake,multisplit --dpi-desync-split-seqovl=681 --dpi-desync-split-pos=1 --dpi-desync-fooling=ts --dpi-desync-repeats=8 --dpi-desync-split-seqovl-pattern=tls_clienthello_www_google_com.bin --dpi-desync-fake-tls-mod=rnd,dupsid,sni=www.google.com"""
    },
    "general_fake_tls_auto_alt2_184": {
        "name": "general (fake TLS auto alt2) 1.8.4",
        "description": "multisplit seqovl 681 pos 1 seqovl pattern",
        "author": "Flowseal",
        "label": None,
        "args": f"""--dpi-desync=fake,multisplit --dpi-desync-split-seqovl=681 --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-badseq-increment=10000000 --dpi-desync-repeats=8 --dpi-desync-split-seqovl-pattern=tls_clienthello_www_google_com.bin --dpi-desync-fake-tls-mod=rnd,dupsid,sni=www.google.com"""
    },
    "general_fake_tls_auto_184": {
        "name": "general (fake TLS auto) 1.8.4",
        "description": "multisplit seqovl 681 pos 1 seqovl pattern",
        "author": "Flowseal",
        "label": None,
        "args": f"""--dpi-desync=fake,multidisorder --dpi-desync-split-pos=1,midsld --dpi-desync-repeats=11 --dpi-desync-fooling=badseq --dpi-desync-fake-tls-mod=rnd,dupsid,sni=sun6-21.userapi.com"""
    },
    "dronatar_4_3": {
        "name": "Dronatar 4.3",
        "description": "fake fake-tls=0x00, repeats=6 badseq,hopbyhop2",
        "author": "Dronatar",
        "label": LABEL_RECOMMENDED,
        "args": f"""--dpi-desync=fake --dpi-desync-fake-tls-mod=none --dpi-desync-repeats=6 --dpi-desync-fooling=badseq,hopbyhop2"""
    },
    "launcher_zapret_2_9_1_v1": {
        "name": "Launcher zapret 2.9.1 v1",
        "description": "fake multidisorder pos 7 fake-tls=0F0F0F0F fake-tls=3.bin badseq,autottl 2:2-12",
        "author": "Dronatar",
        "label": LABEL_RECOMMENDED,
        "args": f"""--dpi-desync=fake,multidisorder --dpi-desync-split-pos=7,sld+1 --dpi-desync-fake-tls=0x0F0F0F0F --dpi-desync-fake-tls=3.bin --dpi-desync-fake-tls-mod=rnd,dupsid,sni=fonts.google.com --dpi-desync-fooling=badseq --dpi-desync-autottl 2:2-12"""
    },
    "fake_md5sig_fake_tls": {
        "name": "Launcher zapret 2.9.1 v2",
        "description": "Базовая десинхронизация md5sig с фейком tls",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake --dpi-desync-fooling=md5sig --dpi-desync-fake-tls-mod=rnd,rndsni,padencap"""
    },
    "launcher_zapret_2_9_1_v3": {
        "name": "Launcher zapret 2.9.1 v3",
        "description": "multidisorder pos 1 midsld fake-tls=3.bin autottl",
        "author": "Dronatar",
        "label": LABEL_RECOMMENDED,
        "args": f"""--dpi-desync=multidisorder --dpi-desync-split-pos=1,midsld --dpi-desync-fake-tls=3.bin --dpi-desync-autottl"""
    },
    "launcher_zapret_2_9_1_v4": {
        "name": "Launcher zapret 2.9.1 v4",
        "description": "multisplit pos 1 seqovl 681 pattern 4.bin dpi-desync-repeats=2",
        "author": "Dronatar",
        "label": LABEL_RECOMMENDED,
        "args": f"""--dpi-desync=multisplit --dpi-desync-repeats=2 --dpi-desync-split-seqovl=681 --dpi-desync-split-pos=1 --dpi-desync-split-seqovl-pattern=4.bin"""
    },
    "multidisorder_seqovl_midsld": {
        "name": "multidisorder seqovl midsld",
        "description": "Самая простая стратегия multisplit для YouTube",
        "author": None,
        "label": LABEL_RECOMMENDED,
        "args": f"""--dpi-desync=multidisorder --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=midsld-1"""
    },
    "other_seqovl_2": {
        "name": "multidisorder seqovl 211 & pattern 5",
        "description": "Потом опишу подробнее",
        "author": "hz",
        "label": LABEL_RECOMMENDED,
        "args": f"""--dpi-desync=multidisorder --dpi-desync-split-seqovl=211 --dpi-desync-split-seqovl-pattern=tls_clienthello_5.bin"""
    },
    "multisplit_226_pattern_18": {
        "name": "multisplit seqovl 226",
        "description": "Мультисплит стратегия с фуллингом pattern и повтором 9",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=multisplit --dpi-desync-split-seqovl=226 --dpi-desync-split-seqovl-pattern=tls_clienthello_18.bin --dup=2 --dup-cutoff=n3"""
    },
    "multisplit_226_pattern_google_Com": {
        "name": "multisplit seqovl 226 v2",
        "description": "Мультисплит стратегия с фуллингом pattern и повтором 9",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=multisplit --dpi-desync-split-seqovl=226 --dpi-desync-split-seqovl-pattern=tls_clienthello_www_google_com.bin --dup=2 --dup-cutoff=d1"""
    },
    "multisplit_308_pattern": {
        "name": "multisplit seqovl 308 с парттерном 9",
        "description": "Мультисплит стратегия с фуллингом badseq нарезкой и повтором 9",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=multisplit --dpi-desync-split-seqovl=308 --dpi-desync-split-seqovl-pattern=tls_clienthello_9.bin --dup=2 --dup-cutoff=n3"""
    },
    "multisplit_split_pos_1": {
        "name": "multisplit split pos 1",
        "description": "Потом опишу подробнее",
        "author": "hz",
        "label": LABEL_RECOMMENDED,
        "args": f"""--dpi-desync=multisplit --dpi-desync-split-pos=1"""
    },
    "datanoack": {
        "name": "datanoack",
        "description": "Потом опишу подробнее",
        "author": "hz",
        "label": LABEL_RECOMMENDED,
        "args": f"""--dpi-desync-fooling=datanoack"""
    },
    "multisplit_datanoack": {
        "name": "multisplit datanoack",
        "description": "Потом опишу подробнее",
        "author": "hz",
        "label": LABEL_RECOMMENDED,
        "args": f"""--dpi-desync=multisplit --dpi-desync-fooling=datanoack"""
    },
    "multisplit_datanoack_split_pos_1": {
        "name": "multisplit datanoack split pos 1",
        "description": "Потом опишу подробнее",
        "author": "hz",
        "label": LABEL_RECOMMENDED,
        "args": f"""--dpi-desync=multisplit --dpi-desync-fooling=datanoack --dpi-desync-split-pos=1"""
    },
    "other_seqovl_fakedsplit_ttl2": {
        "name": "fakedsplit ttl2",
        "description": "Потом опишу подробнее",
        "author": "hz",
        "label": LABEL_RECOMMENDED,
        "args": f"""--dpi-desync=fake,fakedsplit --dpi-desync-ttl=2 --dpi-desync-split-pos=1 --dpi-desync-fake-tls=0x00000000 --dpi-desync-fake-tls=! --dpi-desync-fake-tls-mod=rnd,rndsni,dupsid"""
    },
    "fakeddisorder_datanoack_1": {
        "name": "FakedDisorder datanoack",
        "description": "Базовая стратегия FakedDisorder с datanoack",
        "author": None,
        "label": LABEL_RECOMMENDED,
        "args": f"""--dpi-desync=fake,fakeddisorder --dpi-desync-fooling=datanoack --dpi-desync-split-pos=midsld --dpi-desync-fake-tls=0x00000000"""
    },
    "other_multidisorder": {
        "name": "multidisorder 6 md5sig",
        "description": "Потом опишу подробнее",
        "author": "hz",
        "label": LABEL_STABLE,
        "args": f"""--dpi-desync=fake,multidisorder --dpi-desync-split-pos=1,midsld --dpi-desync-repeats=6 --dpi-desync-fooling=md5sig"""
    },
    "fake_fakedsplit_autottl_2": {
        "name": "fake fakedsplit badseq (рекомендуется для 80 порта)",
        "description": "",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,fakedsplit --dpi-desync-autottl=2 --dpi-desync-fooling=badseq"""
    },
    "multisplit_seqovl_2_midsld": {
        "name": "fake multisplit seqovl 2 midsld",
        "description": "Потом опишу подробнее",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,multisplit --dpi-desync-split-seqovl=2 --dpi-desync-split-pos=1,midsld --dpi-desync-fake-http=0x0F0F0F0F --dpi-desync-fooling=md5sig"""
    },
    "multisplit_17": {
        "name": "YTDisBystro 3.4",
        "description": "Мульти нарезка с md5sig и фейком TLS",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,multisplit --dpi-desync-split-pos=2,midsld --dpi-desync-fake-tls=tls_clienthello_17.bin --dpi-desync-fake-tls-mod=rnd,dupsid --dpi-desync-fooling=md5sig --dpi-desync-autottl --dup=2 --dup-fooling=md5sig --dup-autottl --dup-cutoff=n3"""
    },
    "other5": {
        "name": "multidisorder datanoack deepseek",
        "description": "Потом опишу подробнее",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,multidisorder --dpi-desync-fooling=datanoack --dpi-desync-split-pos=midsld --dpi-desync-fake-tls=tls_clienthello_chat_deepseek_com.bin"""
    },
    "multisplit_1_midsld": {
        "name": "multisplit seqovl 1 и midsld",
        "description": "Базовая мультисплит с midsld",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=multisplit --dpi-desync-split-pos=1,midsld"""
    },
    "fake_multidisorder_1_split_pos_1": {
        "name": "fake multidisorder badsum split pos 1",
        "description": "Базовая мультисплит с midsld",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,multidisorder --dpi-desync-fooling=badsum --dpi-desync-split-pos=1"""
    },
    "multisplit_seqovl_midsld": {
        "name": "multisplit seqovl midsld",
        "description": "Самая простая стратегия multisplit для Google",
        "author": None,
        "label": LABEL_RECOMMENDED,
        "args": f"""--dpi-desync=multisplit --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=midsld-1"""
    },
    "bolvan_md5sig": {
        "name": "BolVan md5sig 11",
        "description": "Другой метод фуллинга + большее число повторений",
        "author": "OrigBolvan",
        "label": None,
        "args": f"""--dpi-desync=fake,multidisorder --dpi-desync-split-pos=1,midsld --dpi-desync-repeats=11 --dpi-desync-fooling=md5sig"""
    },
    "bolvan_md5sig_2": {
        "name": "BolVan v3",
        "description": "Другой метод фуллинга + большее число повторений + tls от гугла",
        "author": "Уфанет",
        "label": None,
        "args": f"""--dpi-desync=fake,multidisorder --dpi-desync-split-pos=1,midsld --dpi-desync-repeats=11 --dpi-desync-fooling=md5sig  --dpi-desync-fake-tls-mod=rnd,dupsid,sni=www.google.com"""
    },
    "bolvan_fake_tls": {
        "name": "BolVan fake TLS 4",
        "description": "Используется фейковый Clienthello",
        "author": "OrigBolvan",
        "label": None,
        "args": f"""--dpi-desync=fake,multidisorder --dpi-desync-split-pos=1,midsld --dpi-desync-repeats=4 --dpi-desync-fake-tls=tls_clienthello_18.bin --dpi-desync-fooling=badseq"""
    },
    "fake_multisplit_seqovl_md5sig": {
        "name": "fake multisplit и seqovl 1 md5sig",
        "description": "Используется multisplit и seqovl 1",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,multisplit --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=midsld-1 --dpi-desync-fooling=md5sig,badseq --dpi-desync-fake-tls=tls_clienthello_4.bin --dpi-desync-ttl=2"""
    },
    "multisplit_1": {
        "name": "Мультисплит и смещение +1",
        "description": "Базовая стратегия десинхронизации multisplit",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=multisplit --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=sld+1"""
    },
    "multisplit_2": {
        "name": "Мультисплит и смещение -1",
        "description": "Базовая стратегия десинхронизации multisplit",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=multisplit --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=sld-1"""
    },
    "multidisorder_fake_tls_1": {
        "name": "YtDisBystro 3.4 (v4)",
        "description": "multidisorder 7 Fake TLS fonts и badseq",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,multidisorder --dpi-desync-split-pos=7,sld+1 --dpi-desync-fake-tls=0x0F0F0F0F --dpi-desync-fake-tls=tls_clienthello_4.bin --dpi-desync-fake-tls-mod=rnd,dupsid,sni=fonts.google.com --dpi-desync-fooling=badseq --dpi-desync-autottl"""
    },
    "multidisorder_fake_tls_2": {
        "name": "multidisorder 7 Fake TLS calendar и badseq",
        "description": "Кастомная и сложная стратегия с фейком calendar",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,multidisorder --dpi-desync-split-pos=7,sld+1 --dpi-desync-fake-tls=0x0F0F0F0F --dpi-desync-fake-tls=tls_clienthello_4.bin --dpi-desync-fake-tls-mod=rnd,dupsid,sni=calendar.google.com --dpi-desync-fooling=badseq --dpi-desync-autottl"""
    },
    "syndata": {
        "name": "syndata",
        "description": "Экспериментальная стратегия с ЧИСТОЙ syndata",
        "author": "Flowseal",
        "label": LABEL_CAUTION,
        "args": f"""--dpi-desync=syndata"""
    },
    "multisplit_md5sig": {
        "name": "multisplit и md5sig",
        "description": "Экспериментальная стратегия multisplit и md5sig",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,multisplit --dpi-desync-split-pos=sld+1 --dpi-desync-fake-tls=0x0F0F0E0F --dpi-desync-fake-tls=tls_clienthello_9.bin --dpi-desync-fake-tls-mod=rnd,dupsid --dpi-desync-fooling=md5sig --dpi-desync-autottl --dup=2 --dup-fooling=md5sig --dup-autottl --dup-cutoff=n3""" # раньше тут было syndata --dpi-desync-fake-syndata=tls_clienthello_7.bin
    },
    "fake_multidisorder_seqovl_fake_tls": {
        "name": "fake multidisorder seqovl fake tls",
        "description": "ОЧЕНЬ сложная стратегия с фейком TLS и seqovl",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,multidisorder --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=sld+1 --dpi-desync-fake-tls=0x0F0F0E0F --dpi-desync-fake-tls=tls_clienthello_9.bin --dpi-desync-fake-tls-mod=rnd,dupsid --dpi-desync-fooling=md5sig --dpi-desync-autottl --dup=2 --dup-fooling=md5sig --dup-autottl --dup-cutoff=n3"""
    },
    "syndata_md5sig_2": {
        "name": "multisplit и md5sig 9",
        "description": "Стандартный multisplit и md5sig и фейк TLS 9",
        "author": "hz",
        "label": LABEL_CAUTION,
        "args": f"""--ipcache-hostname --dpi-desync=syndata,fake,multisplit --dpi-desync-split-pos=sld+1 --dpi-desync-fake-syndata=tls_clienthello_7.bin --dpi-desync-fake-tls=0x0F0F0E0F --dpi-desync-fake-tls=tls_clienthello_9.bin --dpi-desync-fake-tls-mod=rnd,dupsid --dpi-desync-fooling=md5sig --dpi-desync-autottl --dup=2 --dup-fooling=md5sig --dup-autottl --dup-cutoff=n3"""
    },
    "multisplit_fake_tls_md5sig": {
        "name": "multisplit и md5sig 1",
        "description": "Стандартный multisplit и md5sig и фейк TLS 1",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,multisplit --dpi-desync-split-pos=sld+1 --dpi-desync-fake-tls=0x0F0F0E0F --dpi-desync-fake-tls=tls_clienthello_1.bin --dpi-desync-fake-tls-mod=rnd,dupsid --dpi-desync-fooling=md5sig --dpi-desync-autottl --dup=2 --dup-fooling=md5sig --dup-autottl --dup-cutoff=n3"""
    },
    "multisplit_seqovl_pos": {
        "name": "multisplit seqovl с split pos",
        "description": "Базовый multisplit и seqovl с фейками и нарезкой",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,multisplit --dpi-desync-split-seqovl=2 --dpi-desync-split-pos=3 --dpi-desync-fake-tls=tls_clienthello_2.bin --dpi-desync-ttl=3"""
    },
    "multisplit_seqovl_pos_2": {
        "name": "multisplit seqovl с split pos и badseq",
        "description": "Базовый multisplit и seqovl с фейками, нарезкой и  badseq",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,multisplit --dpi-desync-fooling=badseq --dpi-desync-split-seqovl=2 --dpi-desync-split-pos=2 --dpi-desync-fake-tls=tls_clienthello_2n.bin --dpi-desync-fake-tls-mod=rnd --dpi-desync-autottl"""
    },
    "multidisorder_repeats_md5sig": {
        "name": "original bol-van v2",
        "description": "multidisorder с fake tls mod",
        "author": "bol-van",
        "label": None,
        "args": f"""--dpi-desync=fake,multidisorder --dpi-desync-split-pos=1,midsld --dpi-desync-repeats=11 --dpi-desync-fooling=md5sig --dpi-desync-fake-tls-mod=rnd,dupsid,sni=www.google.com"""
    },
    "multidisorder_repeats_md5sig_2": {
        "name": "multidisorder с повторами и md5ig",
        "description": "multidisorder с fake tls clienthello",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,multidisorder --dpi-desync-split-pos=1,midsld --dpi-desync-repeats=11 --dpi-desync-fooling=md5sig --dpi-desync-fake-tls=tls_clienthello_www_google_com.bin"""
    },
    "general_alt3183": {
        "name": "general (alt v3) 1.6.1",
        "description": "split pos 1 autottl badseq repeats 8",
        "author": "Flowseal",
        "label": None,
        "args": f"""--dpi-desync=split --dpi-desync-split-pos=1 --dpi-desync-autottl --dpi-desync-fooling=badseq --dpi-desync-repeats=8"""
    },
    "general_alt4_161": {
        "name": "general (alt v4) 1.6.1",
        "description": "fake split2 repeats 6 md5sig tls google",
        "author": "Flowseal",
        "label": None,
        "args": f"""--dpi-desync=fake,split2 --dpi-desync-repeats=6 --dpi-desync-fooling=md5sig --dpi-desync-fake-tls=tls_clienthello_www_google_com.bin"""
    },
    "general_alt6_181": {
        "name": "general (alt v6) 1.8.1",
        "description": "split2 repeats 2 seqovl 681 pos 1 badseq hopbyhop2",
        "author": "Flowseal",
        "label": None,
        "args": f"""--dpi-desync=split2 --dpi-desync-repeats=2 --dpi-desync-split-seqovl=681 --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq,hopbyhop2 --dpi-desync-split-seqovl-pattern=tls_clienthello_www_google_com.bin"""
    },
    "ankddev10": {
        "name": "aankddev (v10)",
        "description": "syndata multidisorder split pos 4 repeats 10 md5sig fake tls vk kyber",
        "author": "hz",
        "label": LABEL_CAUTION,
        "args": f"""--ipcache-hostname --dpi-desync=syndata,multidisorder --dpi-desync-split-pos=4 --dpi-desync-repeats=10 --dpi-desync-fooling=md5sig --dpi-desync-fake-tls=tls_clienthello_vk_com_kyber.bin"""
    },
    "split2_seqovl_vk": {
        "name": "Устаревший split2 с clienthello от VK",
        "description": "split2 и 625 seqovl с sniext и vk ttl 2 от конторы пидорасов",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,split2 --dpi-desync-split-seqovl=625 --dpi-desync-split-tls=sniext --dpi-desync-fake-tls=tls_clienthello_vk_com.bin --dpi-desync-ttl=2"""
    },
    "split2_seqovl_google": {
        "name": "Устаревший split2 с clienthello от google",
        "description": "split2 и 1 seqovl с sniext и google ttl 4",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,split2 --dpi-desync-split-seqovl=1 --dpi-desync-split-tls=sniext --dpi-desync-fake-tls=tls_clienthello_www_google_com.bin --dpi-desync-ttl=4"""
    },
    "split2_split": {
        "name": "Устаревший split2 split",
        "description": "Базовый split2 и нарезка",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,split2 --dpi-desync-split-seqovl=2 --dpi-desync-split-pos=3"""
    },
    "split2_seqovl_652": {
        "name": "split2 seqovl 652",
        "description": "Устаревший split2 с seqovl 652 и паттерном 4",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,split2 --dpi-desync-split-seqovl=652 --dpi-desync-split-pos=3,midsld-1 --dpi-desync-split-seqovl-pattern=tls_clienthello_4.bin"""
    },
    "split2_split_google": {
        "name": "Устаревший split2 split seqovl google",
        "description": "Базовый split2 и нарезка с fake tls google",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,split2 --dpi-desync-split-seqovl=2 --dpi-desync-split-pos=3 --dpi-desync-fake-tls=tls_clienthello_www_google_com.bin --dpi-desync-ttl=3"""
    },
    "split2_split_2": {
        "name": "Устаревший split2 split seqovl 2",
        "description": "Базовый split2 и нарезка с fake tls 2",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,split2 --dpi-desync-split-seqovl=2 --dpi-desync-split-pos=3 --dpi-desync-fake-tls=tls_clienthello_2.bin --dpi-desync-autottl=2"""
    },
    "fake_split2": {
        "name": "Устаревший fake split2 seqovl 1",
        "description": "fake и split2, нарезка с fake tls 2",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=fake,split2 --dpi-desync-split-seqovl=1 --dpi-desync-split-tls=sniext --dpi-desync-fake-tls=tls_clienthello_3.bin --dpi-desync-ttl=2"""
    },
    "split_seqovl": {
        "name": "Устаревший split и seqovl",
        "description": "Базовый split и seqovl",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=split --dpi-desync-split-seqovl=1 --dpi-desync-split-tls=sniext --dpi-desync-fake-tls=tls_clienthello_www_google_com.bin --dpi-desync-ttl=1"""
    },
    "split_pos_badseq_10": {
        "name": "split badseq 10 и cutoff",
        "description": "split и badseq разрез и 10 повторов",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=split --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-cutoff=d2 --dpi-desync-ttl=3"""
    },
    "split_pos_3": {
        "name": "split pos 3 и повторы",
        "description": "split разрез в 3 и 4 повтора",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=split --dpi-desync-split-pos=3 --dpi-desync-repeats=4 --dpi-desync-autottl=1"""
    },
    "multidisorder_midsld": {
        "name": "multidisorder midsld",
        "description": "Базовая стратегия multidisorder и midsld",
        "author": None,
        "label": LABEL_RECOMMENDED,
        "args": f"""--dpi-desync=multidisorder --dpi-desync-split-pos=1,midsld""" # Launcher zapret 3.0.0 Extreme Mode | multisplit pos 1 seqovl 681 pattern 4.bin dpi-desync-repeats=2
    },
    "multidisorder_midsld_syndata": {
        "name": "syndata multidisorder midsld",
        "description": "syndata и multidisorder и midsld (работает на все сайты!)",
        "author": None,
        "label": LABEL_CAUTION,
        "args": f"""--dpi-desync=syndata,multidisorder --dpi-desync-split-pos=1,midsld"""
    },
    "googlevideo_fakedsplit": {
        "name": "GoogleVideo FakedSplit badseq",
        "description": "Базовая стратегия FakedSplit для GoogleVideo с badseq",
        "author": None,
        "label": LABEL_RECOMMENDED,
        "args": f"""--dpi-desync=fakedsplit --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-ttl=4"""
    },
    "googlevideo_split": {
        "name": "GoogleVideo Split cutoff",
        "description": "Стратегия Split для GoogleVideo с cutoff",
        "author": None,
        "label": None,
        "args": f"""--dpi-desync=split --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-cutoff=d2 --dpi-desync-ttl=4"""
    },
    "googlevideo_multidisorder": {
        "name": "GoogleVideo MultiDisorder Complex",
        "description": "Сложная стратегия MultiDisorder с множественными позициями разреза",
        "author": None,
        "label": LABEL_STABLE,
        "args": f"""--dpi-desync=multidisorder --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=1,host+2,sld+2,sld+5,sniext+1,sniext+2,endhost-2"""
    },
    "googlevideo_multisplit_pattern": {
        "name": "GoogleVideo MultiSplit Pattern 7",
        "description": "MultiSplit с паттерном ClientHello 7",
        "author": None,
        "label": None,
        "args": f"""--dpi-desync=multisplit --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=2,midsld-2 --dpi-desync-split-seqovl-pattern=tls_clienthello_7.bin"""
    },
    "googlevideo_fakeddisorder": {
        "name": "GoogleVideo FakedDisorder AutoTTL",
        "description": "FakedDisorder с паттерном и AutoTTL",
        "author": None,
        "label": None,
        "args": f"""--dpi-desync=fakeddisorder --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=2,midsld-2 --dpi-desync-fakedsplit-pattern=tls_clienthello_7.bin --dpi-desync-fooling=badseq --dpi-desync-autottl"""
    },
    "googlevideo_fakedsplit_simple": {
        "name": "GoogleVideo FakedSplit Simple",
        "description": "Простая стратегия FakedSplit с позицией 1",
        "author": None,
        "label": None,
        "args": f"""--dpi-desync=fakedsplit --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=8 --dpi-desync-autottl"""
    },
    "googlevideo_split_aggressive": {
        "name": "GoogleVideo Split Aggressive",
        "description": "Агрессивная стратегия Split с множеством повторов",
        "author": None,
        "label": LABEL_CAUTION,
        "args": f"""--dpi-desync=split --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=15 --dpi-desync-cutoff=d3 --dpi-desync-ttl=3"""
    },
    "googlevideo_multidisorder_midsld": {
        "name": "GoogleVideo MultiDisorder MidSLD",
        "description": "MultiDisorder с разрезом по середине SLD",
        "author": None,
        "label": None,
        "args": f"""--dpi-desync=multidisorder --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=midsld,midsld+2 --dpi-desync-fooling=badseq --dpi-desync-repeats=10"""
    },
    "googlevideo_fake_multisplit": {
        "name": "GoogleVideo Fake+MultiSplit",
        "description": "Комбинация Fake и MultiSplit",
        "author": None,
        "label": None,
        "args": f"""--dpi-desync=fake,multisplit --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=1,sld+1 --dpi-desync-fake-tls=tls_clienthello_www_google_com.bin --dpi-desync-fooling=badseq"""
    },
    "fake_fakedsplit_md5sig_80_port": {
        "name": "Fake FakedSplit MD5Sig increment 10M",
        "description": "Особая стратегия Fake+FakedSplit с двойным MD5Sig и большим инкрементом для обхода детектов",
        "author": None,
        "label": None,
        "args": f"""--dpi-desync=fake,fakedsplit --dpi-desync-fooling=md5sig --dup=1 --dup-cutoff=n2 --dup-fooling=md5sig --dpi-desync-split-pos=midsld --dpi-desync-badseq-increment=10000000"""
    },
    "fake_multisplit_datanoack_wssize_midsld": {
        "name": "GoogleVideo Fake+MultiSplit datanoack wssize midsld",
        "description": "Экспериментальная стратегия Fake+MultiSplit с datanoack, wssize и разрезом по середине SLD",
        "author": None,
        "label": LABEL_CAUTION,
        "args": f"""---dpi-desync=fake,multisplit --dpi-desync-fooling=datanoack --wssize 1:6 --dpi-desync-split-pos=midsld --dpi-desync-fake-tls-mod=rnd,dupsid,rndsni,padencap"""
    },
    "syndata_1": {
        "name": "syndata 4",
        "description": "Потом опишу подробнее",
        "author": "hz",
        "label": LABEL_RECOMMENDED,
        "args": f"""--dpi-desync=syndata --dpi-desync-fake-syndata=tls_clienthello_4.bin --dpi-desync-autottl"""
    },
    "syndata_4_badseq": {
        "name": "syndata 4 badseq",
        "description": "Потом опишу подробнее",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=syndata --dpi-desync-fake-syndata=tls_clienthello_4.bin --dpi-desync-fooling=badseq"""
    },
    "syndata_7_n3": {
        "name": "syndata 7 n3",
        "description": "Потом опишу подробнее",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=syndata --dpi-desync-fake-syndata=tls_clienthello_7.bin --dup=2 --dup-cutoff=n3"""
    },
    "syndata_syn_packet_n3": {
        "name": "syndata syn_packet.bin n3",
        "description": "Потом опишу подробнее",
        "author": "hz",
        "label": None,
        "args": f"""--dpi-desync=syndata --dpi-desync-fake-syndata=syn_packet.bin --dup=2 --dup-cutoff=n3"""
    }
}