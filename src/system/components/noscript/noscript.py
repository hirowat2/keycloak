from django_components import Component, register, types


@register("noscript")
class NoScript(Component):
    template: types.django_html = """
      <noscript>Your browser does not support JavaScript!</noscript>
    """

    css: types.css = """
    """

    js: types.js = """
    """
