install:
	mkdir -p ${DESTDIR}/usr/share/applications/hildon
	cp maemo/fmvis.desktop ${DESTDIR}/usr/share/applications/hildon/
	mkdir -p ${DESTDIR}/usr/share/icons/hicolor/scalable/apps
	cp maemo/fmvis.png ${DESTDIR}/usr/share/icons/hicolor/scalable/apps/
	
	mkdir -p ${DESTDIR}/opt/fmvis/
	cp src/* ${DESTDIR}/opt/fmvis/
	chmod +x ${DESTDIR}/opt/fmvis/Application.py

clean:
	find . -name "*.pyo" -exec rm "{}" \;
	@true

all:
	@true

