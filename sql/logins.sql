-- name: create-login!
insert into logins(uuid, code, state)
values (:uuid, :code, :state);

-- name: get-login^
select code, state
from logins
where uuid = :uuid;

-- name: delete-login!
delete from logins
where uuid = :uuid;

-- name: clear-old-logins!
delete from logins
where stamp < unixepoch() - :maxage;
