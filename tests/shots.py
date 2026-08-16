import pathlib
from playwright.sync_api import sync_playwright
R = pathlib.Path(__file__).resolve().parent.parent
with sync_playwright() as pw:
    b = pw.chromium.launch(); p = b.new_page(viewport={"width":1200,"height":1000}, device_scale_factor=2)
    p.goto((R/"dist"/"delivery-value-dashboard.html").as_uri()); p.wait_for_timeout(700)
    p.click("#btn-import"); p.wait_for_timeout(300)
    p.screenshot(path=str(R/"docs"/"screenshots"/"import-choose.png"))
    p.set_input_files("#file", str(R/"tests"/"fixtures"/"jira-export.csv"))
    p.wait_for_selector("#step-map:not(.hidden)"); p.wait_for_timeout(300)
    p.screenshot(path=str(R/"docs"/"screenshots"/"import-mapping.png"), full_page=True)
    p.click("#m-preview"); p.wait_for_selector("#step-preview:not(.hidden)"); p.wait_for_timeout(300)
    p.screenshot(path=str(R/"docs"/"screenshots"/"import-preview.png"), full_page=True)
    b.close()
