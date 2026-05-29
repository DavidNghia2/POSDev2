-- Reset the default test account passwords to match the desktop app docs.

update public.users
set password_hash = 'sha256$240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9'
where username = 'admin';

update public.users
set password_hash = 'sha256$866485796cfa8d7c0cf7111640205b83076433547577511d81f8030ae99ecea5'
where username = 'manager';

update public.users
set password_hash = 'sha256$b4c94003c562bb0d89535eca77f07284fe560fd48a7cc1ed99f0a56263d616ba'
where username = 'cashier';
