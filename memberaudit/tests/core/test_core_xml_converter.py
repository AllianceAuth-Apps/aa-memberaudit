from app_utils.testing import NoSocketsTestCase

from memberaudit.core.xml_converter import DEFAULT_FONT_SIZE, eve_xml_to_html
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.tests.testdata.load_locations import load_locations

MODULE_PATH = "memberaudit.core.xml_converter"


class TestXMLConversion(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()

    def test_should_convert_font_tag(self):
        input = '<font size="13" color="#b3ffffff">Character</font>'
        expected = '<span style="font-size: 13px">Character</span>'
        self.assertHTMLEqual(eve_xml_to_html(input), expected)

    def test_should_remove_loc_tag(self):
        input = "<loc>Character</loc>"
        expected = "Character"
        self.assertHTMLEqual(eve_xml_to_html(input), expected)

    def test_add_target_to_normal_links(self):
        input = (
            '<a href="http://www.google.com" target="_blank">https://www.google.com</a>'
        )
        self.assertHTMLEqual(eve_xml_to_html(input), input)

    def test_should_convert_character_link(self):
        input = '<a href="showinfo:1376//1001">Bruce Wayne</a>'
        expected = '<a href="https://evewho.com/character/1001" target="_blank">Bruce Wayne</a>'
        self.assertHTMLEqual(eve_xml_to_html(input), expected)

    def test_should_convert_corporation_link(self):
        input = '<a href="showinfo:2//2001">Wayne Technologies</a>'
        expected = (
            '<a href="https://evemaps.dotlan.net/corp/Wayne_Technologies" '
            'target="_blank">Wayne Technologies</a>'
        )
        self.assertHTMLEqual(eve_xml_to_html(input), expected)

    def test_should_convert_alliance_link(self):
        input = '<a href="showinfo:16159//3001">Wayne Enterprises</a>'
        expected = (
            '<a href="https://evemaps.dotlan.net/alliance/Wayne_Enterprises" '
            'target="_blank">Wayne Enterprises</a>'
        )
        self.assertHTMLEqual(eve_xml_to_html(input), expected)

    def test_should_convert_solar_system_link(self):
        input = '<a href="showinfo:5//30004984">Abune</a>'
        expected = '<a href="https://evemaps.dotlan.net/system/Abune" target="_blank">Abune</a>'
        self.assertHTMLEqual(eve_xml_to_html(input), expected)

    def test_should_convert_station_link(self):
        input = (
            '<a href="showinfo:52678//60003760">'
            "Jita IV - Moon 4 - Caldari Navy Assembly Plant</a>"
        )
        expected = (
            '<a href="https://evemaps.dotlan.net/station/Jita_IV_-_Moon_4_-_Caldari_Navy_Assembly_Plant" '
            'target="_blank">Jita IV - Moon 4 - Caldari Navy Assembly Plant</a>'
        )
        self.assertHTMLEqual(eve_xml_to_html(input), expected)

    def test_should_convert_kill_link(self):
        input = (
            '<a href="killReport:84900666:9e6fe9e5392ff0cfc6ab956677dbe1deb69c4b04">'
            "Kill: Yuna Kobayashi (Badger)</a>"
        )
        expected = (
            '<a href="https://zkillboard.com/kill/84900666/" '
            'target="_blank">Kill: Yuna Kobayashi (Badger)</a>'
        )
        self.assertHTMLEqual(eve_xml_to_html(input), expected)

    # def test_should_disable_unknown_types(self):
    #     input = '<a href="showinfo:601//30004984">Abune</a>'
    #     expected = '<a href="#">Abune</a>'
    #     self.assertHTMLEqual(eve_xml_to_html(input), expected)

    def test_should_disable_unknown_links(self):
        input = '<a href="unknown">Abune</a>'
        expected = '<a href="#">Abune</a>'
        self.assertHTMLEqual(eve_xml_to_html(input), expected)

    def test_should_set_default_font(self):
        input = 'First<br><font size="20">Second</font>Third'
        expected = (
            '<span style="font-size: 13px">First</span>'
            '<br><span style="font-size: 20px">Second</span>'
            '<span style="font-size: 13px">Third</span>'
        )
        self.assertHTMLEqual(eve_xml_to_html(input, add_default_style=True), expected)

    def test_should_remove_comment(self):
        input = "<u>First<!--<script>badcall();</script>--></u>"
        expected = "<u>First</u>"
        self.assertHTMLEqual(eve_xml_to_html(input), expected)

    def test_should_remove_normal_script(self):
        input = "<b>This is a <script>bad_attempt()</script> at injection</b>"
        expected = "<b>This is a bad_attempt() at injection</b>"
        self.assertHTMLEqual(eve_xml_to_html(input), expected)

    # \ufe64 and \ufe65 are two examples of characters that normalize under NFKC to < >
    def test_should_remove_confusable_script(self):
        input = "<i>Yet another \ufe64script\ufe65attempted()\ufe64/script\ufe65 injection</i>"
        expected = "<i>Yet another attempted() injection</i>"
        self.assertHTMLEqual(eve_xml_to_html(input), expected)

    def test_should_move_valid_children_out(self):
        input = "<u>Test <div><i>it</i> <h1>out</h1></div> okay?</u>"
        expected = "<u>Test <i>it</i> out okay?</u>"
        self.assertHTMLEqual(eve_xml_to_html(input), expected)

    def test_should_use_default_font_size(self):
        input = '<font size="invalid">Test</font>'
        expected = f'<span style="font-size: {DEFAULT_FONT_SIZE}px">Test</span>'
        self.assertHTMLEqual(eve_xml_to_html(input), expected)

    def test_should_use_absolute_font_size(self):
        input = '<font size="-13">Test</font>'
        expected = '<span style="font-size: 13px">Test</span>'
        self.assertHTMLEqual(eve_xml_to_html(input), expected)

    def test_should_handle_valid_or_invalid_protocols(self):
        input = '<a href="unsupported://123456">I should just be text</a><br><a href="https://example.org/">I should be a link</a>'
        expected = 'I should just be text<br><a href="https://example.org/" target="_blank">I should be a link</a>'
        self.assertHTMLEqual(eve_xml_to_html(input), expected)

    def test_should_remove_empty_elements(self):
        input = '<font size="13"><font size="10"></font><a href="https://iforgottext.com/"></a>some text</font>'
        expected = '<span style="font-size: 13px">some text</span>'
        self.assertHTMLEqual(eve_xml_to_html(input), expected)
