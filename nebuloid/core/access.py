import os, yaml

class NebuloidAccess:
    def __init__(self, services, base_dir="pages"):
        services.inject_services(self)
        self.base_dir = base_dir
        self.access_rules = {}          # URL -> rules dict

    def mount(self):
        self.access_rules = {}
        for _, routes in self.manifest.data['server']['routes'].items():
            if isinstance(routes, str):
                routes = [routes]  # Take the first route if multiple are defined
            for route_name in routes:
                access_file = os.path.join(self.base_dir, route_name, "access.yaml")
                rules = {}
                if os.path.exists(access_file):
                    with open(access_file, "r") as f:
                        data = yaml.safe_load(f) or {}
                        rules = data
                self.access_rules[route_name] = rules

    def get_access_rule(self, name):
        return self.access_rules.get(name, {})
    
    def can_access(self, route_name, user_access_data):
        rules = self.get_access_rule(route_name).get("access", {})
        if not rules:
            return True, "Open Access"  # No rules means open access

        user_role = user_access_data.get("role")
        logged_in = user_access_data.get("logged_in", False)

        # Check 'login_required' rule
        if rules.get("login_required") and not logged_in:
            return False, "login_required"

        # Check 'roles' rule
        allowed_roles = rules.get("roles_allowed","*")  # Default to role 0 (public)
        if not self.role_check(user_role, allowed_roles):
            return False, f"Role {user_role} not allowed"

        return True, "Access granted"
    
    def role_check(self, user_role, allowed_roles):
        print("allowed roles", allowed_roles, type(allowed_roles), "User role", user_role)
        if isinstance(allowed_roles, list):
            if user_role not in allowed_roles:
                return False
            else:
                print("User exists")
        elif isinstance(allowed_roles, str):
            if allowed_roles != user_role and allowed_roles != '*':
                return False
            else:
                print("All alowed or specific allowed")
        else:
            print("Unknown roles list type")
        return True