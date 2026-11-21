package com.racas.mostwanted;

import org.junit.Test;
import java.util.Arrays;
import static org.junit.Assert.*;

public class CarConverterScriptParserTest {
    @Test public void recognizesVltEdGameGuardAsMetadata() {
        assertTrue(CarConverter.supportedVltGame("MW"));
        assertTrue(CarConverter.supportedVltGame("mw"));
        assertFalse(CarConverter.supportedVltGame("Carbon"));
        assertFalse(CarConverter.supportedVltGame(""));
    }

    @Test public void preservesQuotedVltEdValues() {
        assertEquals(Arrays.asList("update_field", "pvehicle", "flipcar", "label", "Class", "SPOOLY BOII !!"),
                CarConverter.endTokens("update_field pvehicle flipcar label Class \"SPOOLY BOII !!\""));
    }

    @Test public void preservesQuotedEmptyStrings() {
        assertEquals(Arrays.asList("update_field", "pvehicle", "flipcar", "DefaultPresetRide", ""),
                CarConverter.endTokens("update_field pvehicle flipcar DefaultPresetRide \"\""));
    }

    @Test public void supportsSingleQuotedTokens() {
        assertEquals(Arrays.asList("move_file", "override", "relative", "absolute", "source file", "SOUND/ENGINE/A.gin"),
                CarConverter.endTokens("move_file override relative absolute 'source file' SOUND/ENGINE/A.gin"));
    }
}
