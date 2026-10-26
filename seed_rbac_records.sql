-- Copyright 2026 Allan Brand
--
-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
--
--     http://apache.org
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific permissions and
-- limitations under the License.

BEGIN;

-- 1. CLEANING / INITIALIZATION SAFEGUARDS
DELETE FROM group_permission_association;
DELETE FROM user_group_association;
DELETE FROM permissions;
DELETE FROM groups;

-- 2. SEED CORPORATE GROUP OBJECTS
INSERT INTO groups (id, name) VALUES 
('grp-admin', 'network_admins'),
('grp-operator', 'site_operators'),
('grp-viewer', 'read_only_viewers');

-- 3. SEED GRANULAR OBJECT-LEVEL PERMISSIONS
-- Actions: 'read', 'write', 'execute'
-- Object ID Wildcard '*' permits actions globally across all instances
INSERT INTO permissions (id, object_type, object_id, action) VALUES
-- Admin Tier Permissions (Wildcard Globals)
('perm-adm-proj', 'project', '*', 'write'),
('perm-adm-exec', 'project', '*', 'execute'),
('perm-adm-read', 'project', '*', 'read'),

-- Operator Tier Permissions (Explicit project_Fluxara boundaries)
('perm-op-sync',  'project', 'Fluxara', 'write'),   -- Permitted to trigger Git Sync
('perm-op-exec',  'project', 'Fluxara', 'execute'), -- Permitted to push configs
('perm-op-read',  'project', 'Fluxara', 'read'),

-- Viewer Tier Permissions
('perm-vw-read',  'project', 'Fluxara', 'read');

-- 4. MAP PERMISSIONS TO GROUPS (BRIDGE ASSOCIATIONS)
-- Map Admin Group
INSERT INTO group_permission_association (group_id, permission_id) VALUES
('grp-admin', 'perm-adm-proj'),
('grp-admin', 'perm-adm-exec'),
('grp-admin', 'perm-adm-read');

-- Map Operator Group
INSERT INTO group_permission_association (group_id, permission_id) VALUES
('grp-operator', 'perm-op-sync'),
('grp-operator', 'perm-op-exec'),
('grp-operator', 'perm-op-read');

-- Map Viewer Group
INSERT INTO group_permission_association (group_id, permission_id) VALUES
('grp-viewer', 'perm-vw-read');

-- 5. LINK SEEDED USER TO GROUP TIER
-- Resolves your initial seeded 'net_admin' account (Assumes seed_admin.py has run)
-- Since your seed script auto-generates a UUID for the user, we match via a subquery
INSERT INTO user_group_association (user_id, group_id)
SELECT id, 'grp-admin' FROM users WHERE username = 'net_admin' LIMIT 1;

COMMIT;
