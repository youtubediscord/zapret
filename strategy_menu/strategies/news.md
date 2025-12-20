Реализована поддержка имен профилей (names) и шаблонов профилей (templates).
template - это тоже профиль, принимающий в себя все настройки профиля, но он не идет в список рабочих профилей. Профиль является шаблонными, если в пределах его определения (между --new) присутствует параметр --template.
templates выносятся в отдельный список, чтобы потом из него можно было импортировать настройки. Шаблонному профилю обязательно назначается уникальное имя (–name), после чего его можно импортировать в рабочий профиль (–import=name). Процедура импорта стирает все данные текущего профиля, замещая данными шаблона (включая имя), поэтому --import надо указывать в самом начале после --new. Остальные настройки добавляются к импортированным.

Импорт нескольких шаблонов с наложением не реализован. Однако, шаблоны - тоже полноправные профили и могут импортировать другие шаблоны. Здесь будет 2 шаблона и 1 рабочий профиль, который выполнит 3 инстанса

--template --name t1 --lua-desync=pass --new
--template --import t1 --name t2 --lua-desync=posdebug --new
--import t2 --name template_test --lua-desync=argdebug:test1=1:test2=2

profile 1 (template_test) lua pass( range_in=x0-x0 range_out=a0-a0 payload_type= all)
profile 1 (template_test) lua posdebug( range_in=x0-x0 range_out=a0-a0 payload_type= all)
profile 1 (template_test) lua argdebug(test2="2",test1="1" range_in=x0-x0 range_out=a0-a0 payload_type= all)
template 1 (t1) lua pass( range_in=x0-x0 range_out=a0-a0 payload_type= all)
template 2 (t2) lua pass( range_in=x0-x0 range_out=a0-a0 payload_type= all)
template 2 (t2) lua posdebug( range_in=x0-x0 range_out=a0-a0 payload_type= all)

Убрана детализация пейлоада stun_binding_req.
Любые stun сообщения теперь имеют пейлоад “stun”.