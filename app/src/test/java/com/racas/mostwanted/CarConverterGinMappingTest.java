package com.racas.mostwanted;

import org.junit.Test;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

public class CarConverterGinMappingTest {
    private static byte[] gin(String signature) {
        byte[] data = new byte[64];
        byte[] magic = signature.getBytes(StandardCharsets.US_ASCII);
        System.arraycopy(magic, 0, data, 0, magic.length);
        put32(data, 16, 50);
        put32(data, 20, 2);
        put32(data, 24, 1000);
        put32(data, 28, 48000);
        put32(data, 32, 0);
        put32(data, 36, 100);
        return data;
    }

    private static void put32(byte[] data, int at, long value) {
        for (int i = 0; i < 4; i++) data[at + i] = (byte) (value >>> (i * 8));
    }

    private static File sourceZip(byte[] audio, String sourceName) throws Exception {
        File file = Files.createTempFile("gin-map", ".zip").toFile();
        try (ZipOutputStream zip = new ZipOutputStream(new java.io.FileOutputStream(file))) {
            zip.putNextEntry(new ZipEntry("Assets/Install_Strings"));
            zip.write(("[VERSN2]\\r\\nmove_file override relative absolute " + sourceName
                    + " SOUND\\\\ENGINE\\\\GIN_Test.gin\\r\\n").getBytes(StandardCharsets.ISO_8859_1));
            zip.closeEntry();
            if (audio != null) {
                zip.putNextEntry(new ZipEntry("Assets/" + sourceName));
                zip.write(audio);
                zip.closeEntry();
            }
        }
        return file;
    }

    @Test public void mapsAndValidatesDeclaredGinIntoXboxSoundPath() throws Exception {
        byte[] audio = gin("Gnsu20");
        CarConverter.Kept kept = new CarConverter.Kept();
        kept.car = "TESTCAR";
        kept.sourceAssets = sourceZip(audio, "EngineSource");
        CarConverter.RuntimeAssets result = CarConverter.mappedGinAssets(kept, line -> {});
        assertArrayEquals(audio, result.files.get("SOUND\\ENGINE\\GIN_Test.gin"));
        assertTrue(result.sourcePaths.contains("assets/enginesource"));
    }

    @Test public void repairsOnlyValidatedLegacyGinHeader() throws Exception {
        byte[] audio = gin("Octn21");
        CarConverter.Kept kept = new CarConverter.Kept();
        kept.car = "TESTCAR";
        kept.sourceAssets = sourceZip(audio, "LegacyEngine");
        CarConverter.RuntimeAssets result = CarConverter.mappedGinAssets(kept, line -> {});
        byte[] mapped = result.files.get("SOUND\\ENGINE\\GIN_Test.gin");
        assertEquals('G', mapped[0]);
        assertEquals('O', audio[0]);
        assertEquals(GinAudio.Status.SUPPORTED_HEADER, GinAudio.inspect(mapped).status);
    }

    @Test(expected = CarConverter.Failure.class)
    public void rejectsMissingDeclaredGinSource() throws Exception {
        CarConverter.Kept kept = new CarConverter.Kept();
        kept.car = "TESTCAR";
        kept.sourceAssets = sourceZip(null, "MissingEngine");
        CarConverter.mappedGinAssets(kept, line -> {});
    }

    @Test(expected = CarConverter.Failure.class)
    public void rejectsInvalidDeclaredGinInsteadOfInjectingIt() throws Exception {
        CarConverter.Kept kept = new CarConverter.Kept();
        kept.car = "TESTCAR";
        kept.sourceAssets = sourceZip(new byte[64], "BrokenEngine");
        CarConverter.mappedGinAssets(kept, line -> {});
    }
}
