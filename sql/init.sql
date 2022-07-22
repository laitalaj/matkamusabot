-- name: init#
create table if not exists logins (
    id integer primary key,
    uuid text not null,
    code text not null,
    state text not null,
    stamp integer default (unixepoch())
);
create table if not exists locations (
    id integer primary key,
    addedby integer not null,
    lat double not null,
    lon double not null,
    radius double not null,
    songid text not null,
    songname text not null,
    songartist text not null
);
