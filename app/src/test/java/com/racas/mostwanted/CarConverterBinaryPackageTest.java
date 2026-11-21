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

    @Test public void rejectsTraversalInBinaryMoveFileSource() throws Exception {
        File root = Files.createTempDirectory("binary-source-traversal").toFile();
        File script = new File(root, "install-strings");
        Files.write(script.toPath(), ("[VERSN2]\\n"
                + "move_file override relative absolute ../outside SOUND\\\\ENGINE\\\\bad.gin\\n")
                .getBytes(StandardCharsets.ISO_8859_1));
        Map<String, File> source = new LinkedHashMap<>();
        source.put("Assets/Install_Strings", script);
        try {
            CarConverter.resolveBinaryFiles(source, line -> {});
            fail("source traversal must be rejected");
        } catch (java.io.IOException expected) {
            assertTrue(expected.getMessage().contains("unsafe Binary move_file source"));
        }
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
    @Test public void keepsArchiveRootInstallAttributesBesideBinaryCarsFolder() throws Exception {
        File root = Files.createTempDirectory("binary-root-scripts").toFile();
        Map<String, File> source = new LinkedHashMap<>();
        String[] paths = {
                "Binary/Cars/FLIPCAR/GEOMETRY.BIN",
                "Binary/Cars/FLIPCAR/TEXTURES.BIN",
                "Install_Attributes",
                "FnF Flip Car.nfsms",
                "Assets/Flip_Car_Unlimiter_Data"
        };
        for (int i = 0; i < paths.length; i++) {
            File file = new File(root, "asset-" + i);
            Files.write(file.toPath(), ("asset-" + i).getBytes(StandardCharsets.UTF_8));
            source.put(paths[i], file);
        }

        Map<String, byte[]> carFiles = CarConverter.carFiles(
                source, "Binary/Cars/FLIPCAR/GEOMETRY.BIN");

        assertNotNull("root-level VltEd install script must be retained", carFiles.get("Install_Attributes"));
        assertNotNull("nfsms wrapper is retained as metadata, not selected as VaultEd", carFiles.get("FnF Flip Car.nfsms"));
        assertNotNull("companion Unlimiter assets must be retained", carFiles.get("Assets/Flip_Car_Unlimiter_Data"));
        assertNotNull(carFiles.get("Binary/Cars/FLIPCAR/GEOMETRY.BIN"));
        assertNotNull(carFiles.get("Binary/Cars/FLIPCAR/TEXTURES.BIN"));
    }

}
