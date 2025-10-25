import yaml

async def get_navbar(ctx):
    role = await ctx.orm.get_role(ctx.user['user_id']) if ctx.user else None

    print("Navbar context role:", role)

    with open(ctx.assets_path(f"navbar/structures/{role or 'default'}.yaml"), 'r') as f:
        content = yaml.safe_load(f)
        print("Navbar content:", content)

    return { "navbar": "Dashboard" }

def mount(ctx):
    ctx.register_hook("render_page", get_navbar)