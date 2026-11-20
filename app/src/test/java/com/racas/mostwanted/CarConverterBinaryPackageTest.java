package com.racas.mostwanted;

import org.junit.Test;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.Assert.*;

public class CarConverterBinaryPackageTest {
    @Test public void resolvesExtensionlessBinaryMoveFileAssetsAndKeepsPackageScripts() throws Exception {
        File root = Files.createTempDirectory("binary-package-test").toFile();
        File geometry = new File(root, "geometry");
        File textures = new File(root, "textures");
        File strings = new File(root, "install-strings");
        Files.write(geometry.toPath(), new byte[] {1, 2, 3});
        Files.write(textures.toPath(), new byte[] {4, 5, 6});
        Files.write(strings.toPath(), (
                "[VERSN2]\\n" +
                "move_file override relative absolute Flip_Car_Geometry CARS\\\\FLIPCAR\\\\GEOMETRY.BIN\\n" +
                "move_file override relative absolute Flip_Car_Textures CARS\\\\FLIPCAR\\\\TEXTURES.BIN\\n"
        ).getBytes(StandardCharsets.ISO_8859_1));

        Map<String, File> source = new LinkedHashMap<>();
        source.put("Assets/Flip_Car_Geometry", geometry);
        source.put("Assets/Flip_Car_Textures", textures);
        source.put("Assets/Install_Strings", strings);

        Map<String, File> resolved = CarConverter.resolveBinaryFiles(source, line -> {});
        String geoPath = "Assets/CARS/FLIPCAR/GEOMETRY.BIN";
        String texPath = "Assets/CARS/FLIPCAR/TEXTURES.BIN";
        assertEquals(List.of(geoPath), CarConverter.carPaths(resolved.keySet()));
        assertSame(geometry, resolved.get(geoPath));
        assertSame(textures, resolved.get(texPath));

        Map<String, byte[]> carFiles = CarConverter.carFiles(resolved, geoPath);
        assertArrayEquals(new byte[] {1, 2, 3}, carFiles.get(geoPath));
        assertArrayEquals(new byte[] {4, 5, 6}, carFiles.get(texPath));
        assertArrayEquals(Files.readAllBytes(strings.toPath()), carFiles.get("Assets/Install_Strings"));
    }

    @Test public void resolvesBinaryMoveFileForNonGeometryAssetsAndRejectsTraversal() throws Exception {
        File root = Files.createTempDirectory("binary-move-assets").toFile();
        File sound = new File(root, "sound");
        File script = new File(root, "install-strings");
        Files.write(sound.toPath(), new byte[] {7, 8, 9});
        Files.write(script.toPath(), (
                "[VERSN2]\\n" +
                "move_file override relative absolute Sound_Flip_Car_ACL SOUND\\ENGINE\\GIN_Flip_Car.gin\\n"
        ).getBytes(StandardCharsets.ISO_8859_1));

        Map<String, File> source = new LinkedHashMap<>();
        source.put("Assets/Sound_Flip_Car_ACL", sound);
        source.put("Assets/Install_Strings", script);
        Map<String, File> resolved = CarConverter.resolveBinaryFiles(source, line -> {});

        assertSame(sound, resolved.get("Assets/SOUND/ENGINE/GIN_Flip_Car.gin"));
        assertTrue(CarConverter.wanted("SOUND/ENGINE/GIN_Flip_Car.gin"));
    }
}
