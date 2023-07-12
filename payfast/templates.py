import jinja2 as jinja # Environment, PackageLoader, select_autoescape

env = jinja.Environment(
    loader=jinja.PackageLoader('payfast'),
    autoescape=jinja.select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)




def get_template(name):
    return env.get_template(name)


def render_to_string(template_name, context):
    template = get_template(template_name)
    return template.render(context)
