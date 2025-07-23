create policy "all"
on "public"."users_metadata"
as permissive
for insert
to public
with check (true);



