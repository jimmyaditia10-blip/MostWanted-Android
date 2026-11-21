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
    @Test public void parsesEscapedQuotesAndInlineComments() {
        assertEquals(Arrays.asList("update_field", "pvehicle", "car", "label", "Class", "A \"quoted\" name"),
                CarConverter.endTokens("update_field pvehicle car label Class \"A \\\"quoted\\\" name\" ; comment"));
        assertEquals(Arrays.asList("move_file", "override", "relative", "absolute", "SOUND\\ENGINE\\a.gin", "SOUND\\ENGINE\\b.gin"),
                CarConverter.endTokens("move_file override relative absolute SOUND\\ENGINE\\a.gin SOUND\\ENGINE\\b.gin # note"));
    }

    @Test(expected = IllegalArgumentException.class)
    public void rejectsUnterminatedQuotedTokens() {
        CarConverter.endTokens("update_field pvehicle car label Class \"unfinished");
    }

    @Test public void preservesCommentMarkersInsideUnquotedPaths() {
        assertEquals(Arrays.asList("move_file", "override", "relative", "absolute", "C:\\mods\\car#1.bin", "folder//part.gin"),
                CarConverter.endTokens("move_file override relative absolute C:\\mods\\car#1.bin folder//part.gin"));
    }

    @Test public void stripsWhitespaceDelimitedInlineComments() {
        assertEquals(Arrays.asList("update_field", "pvehicle", "flipcar", "label", "Class", "Brian O'Connor"),
                CarConverter.endTokens("update_field pvehicle flipcar label Class \"Brian O'Connor\" // note"));
        assertEquals(Arrays.asList("delete_node", "pvehicle", "flipcar"),
                CarConverter.endTokens("delete_node pvehicle flipcar ; cleanup"));
    }

    @Test(expected = IllegalArgumentException.class)
    public void rejectsUnterminatedSingleQuotedTokens() {
        CarConverter.endTokens("update_field pvehicle flipcar label 'unfinished");
    }

}
