-- name: create-location!
insert into locations(addedby, lat, lon, radius, songid, songname, songartist)
values (:tgid, :lat, :lon, :radius, :songid, :songname, :songartist);

-- name: get-locations
select addedby, lat, lon, radius, songid, songname, songartist
from locations;
