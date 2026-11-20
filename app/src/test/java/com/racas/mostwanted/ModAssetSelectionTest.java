package com.racas.mostwanted;

import org.junit.Test;

import static org.junit.Assert.*;

public class ModAssetSelectionTest {
    @Test public void keepsAudioAssetsFromNestedPcModFolders() {
        assertTrue(CarConverter.wanted("SOUND/ENGINE/GIN_Flip_Car.gin"));
        assertTrue(CarConverter.wanted("sound/turbo/blowoff.wav"));
        assertTrue(CarConverter.wanted("FRONTEND/FNG/CustomGauge.fng"));
    }

    @Test public void keepsExistingConversionInputs() {
        assertTrue(CarConverter.wanted("CARS/mazda/GEOMETRY.BIN"));
        assertTrue(CarConverter.wanted("CARS/mazda/TEXTURES.BIN"));
        assertTrue(CarConverter.wanted("install.nfsms"));
        assertTrue(CarConverter.wanted("install.end"));
        assertTrue(CarConverter.wanted("UnlimiterData/mazda.ini"));
        assertTrue(CarConverter.wanted("CarParts/mazda/parts.bin"));
    }

    @Test public void doesNotImportUnrelatedOrUninstallFiles() {
        assertFalse(CarConverter.wanted("readme.txt"));
        assertFalse(CarConverter.wanted("uninstall.nfsms"));
        assertFalse(CarConverter.wanted("docs/manual.pdf"));
    }
}
