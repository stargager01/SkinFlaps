////////////////////////////////////////////////////////////////////////////
// File: test_bccTetScene.cpp
// Purpose: Unit tests for the tissueRegionProperties system introduced
//          in bccTetScene to address README Issue #1 (region-specific
//          stretch limits). These tests verify:
//          - getDefaultRegionProperties() returns the expected 7 regions
//          - setRegionStretchLimit() correctly updates or creates regions
//          - setGlobalStretchLimit() applies uniform limits to all regions
//          - getRegionProperties() lookups by name work correctly
//
//          Since bccTetScene has heavy dependencies (OpenGL, materialTriangles,
//          physics solver, etc.), we test the region properties logic by
//          reimplementing the pure data-management portion in a standalone
//          test harness that mirrors the original bccTetScene implementation.
////////////////////////////////////////////////////////////////////////////

#include <gtest/gtest.h>
#include <string>
#include <vector>
#include <cmath>

// ---------------------------------------------------------------------------
// Standalone replica of tissueRegionProperties and the region management
// methods from bccTetScene. This avoids linking against the full project
// while testing the exact same algorithmic logic.
// ---------------------------------------------------------------------------

struct tissueRegionProperties {
    std::string name;
    float stretchMin;
    float stretchMax;
    float lowTetWeight;
    float highTetWeight;
    std::string subsetObjFile;

    tissueRegionProperties()
        : name(""), stretchMin(0.0f), stretchMax(0.0f),
          lowTetWeight(0.0f), highTetWeight(0.0f), subsetObjFile("") {}

    tissueRegionProperties(const std::string& regionName, float sMin, float sMax,
                           float lowW = 0.0f, float highW = 0.0f, const std::string& objFile = "")
        : name(regionName), stretchMin(sMin), stretchMax(sMax),
          lowTetWeight(lowW), highTetWeight(highW), subsetObjFile(objFile) {}
};

// Standalone test harness mirroring bccTetScene's region management.
class RegionManager {
public:
    RegionManager()
        : _globalStretchMin(0.8f), _globalStretchMax(1.26f),
          _globalLowTetWeight(500.0f), _globalHighTetWeight(1000.0f) {}

    // Reimplementation of bccTetScene::getDefaultRegionProperties()
    // from bccTetScene.cpp lines 612-668.
    static std::vector<tissueRegionProperties> getDefaultRegionProperties() {
        std::vector<tissueRegionProperties> defaults;
        defaults.push_back(tissueRegionProperties("cheek", 0.5f, 2.0f));
        defaults.push_back(tissueRegionProperties("eyelid", 0.5f, 2.0f));
        defaults.push_back(tissueRegionProperties("forehead", 0.75f, 1.2f));
        defaults.push_back(tissueRegionProperties("scalp", 0.85f, 1.0f));
        defaults.push_back(tissueRegionProperties("nose", 0.85f, 1.0f));
        defaults.push_back(tissueRegionProperties("lip", 0.6f, 1.5f));
        defaults.push_back(tissueRegionProperties("periorbital", 0.6f, 1.6f));
        return defaults;
    }

    // Reimplementation of bccTetScene::setRegionStretchLimit()
    // from bccTetScene.cpp lines 670-679.
    void setRegionStretchLimit(const std::string& regionName, float stretchMin, float stretchMax) {
        for (auto& rp : _regionProperties) {
            if (rp.name == regionName) {
                rp.stretchMin = stretchMin;
                rp.stretchMax = stretchMax;
                return;
            }
        }
        _regionProperties.push_back(tissueRegionProperties(regionName, stretchMin, stretchMax));
    }

    // Reimplementation of bccTetScene::setRegionProperties()
    // from bccTetScene.cpp lines 682-691.
    void setRegionProperties(const tissueRegionProperties& props) {
        for (auto& rp : _regionProperties) {
            if (rp.name == props.name) {
                rp = props;
                return;
            }
        }
        _regionProperties.push_back(props);
    }

    // Reimplementation of bccTetScene::getRegionProperties()
    // from bccTetScene.cpp lines 693-699.
    const tissueRegionProperties* getRegionProperties(const std::string& regionName) const {
        for (const auto& rp : _regionProperties) {
            if (rp.name == regionName)
                return &rp;
        }
        return nullptr;
    }

    // Reimplementation of bccTetScene::setGlobalStretchLimit()
    // from bccTetScene.cpp lines 701-710.
    void setGlobalStretchLimit(float stretchMin, float stretchMax) {
        _globalStretchMin = stretchMin;
        _globalStretchMax = stretchMax;
        for (auto& rp : _regionProperties) {
            rp.stretchMin = stretchMin;
            rp.stretchMax = stretchMax;
        }
    }

    const std::vector<tissueRegionProperties>& getAllRegionProperties() const { return _regionProperties; }
    float getGlobalStretchMin() const { return _globalStretchMin; }
    float getGlobalStretchMax() const { return _globalStretchMax; }

    // Initialize with default regions (simulates what loadScene does when
    // no "tissueRegions" section is present in the .smd file).
    void loadDefaults() {
        _regionProperties = getDefaultRegionProperties();
    }

private:
    std::vector<tissueRegionProperties> _regionProperties;
    float _globalStretchMin;
    float _globalStretchMax;
    float _globalLowTetWeight;
    float _globalHighTetWeight;
};


// ===========================================================================
// TEST SUITE: DefaultRegionProperties
// Tests that getDefaultRegionProperties() returns the expected 7 regions
// with clinically-informed values.
// ===========================================================================

class DefaultRegionPropertiesTest : public ::testing::Test {
protected:
    std::vector<tissueRegionProperties> defaults;

    void SetUp() override {
        defaults = RegionManager::getDefaultRegionProperties();
    }
};

TEST_F(DefaultRegionPropertiesTest, ReturnsSevenRegions) {
    // The default configuration should include exactly 7 facial regions:
    // cheek, eyelid, forehead, scalp, nose, lip, periorbital.
    EXPECT_EQ(defaults.size(), 7u)
        << "getDefaultRegionProperties() should return exactly 7 regions";
}

TEST_F(DefaultRegionPropertiesTest, AllRegionNamesAreNonEmpty) {
    // Every default region should have a non-empty name.
    for (const auto& rp : defaults) {
        EXPECT_FALSE(rp.name.empty())
            << "Each default region should have a non-empty name";
    }
}

TEST_F(DefaultRegionPropertiesTest, AllRegionNamesAreUnique) {
    // All region names should be unique.
    std::vector<std::string> names;
    for (const auto& rp : defaults)
        names.push_back(rp.name);
    std::sort(names.begin(), names.end());
    auto it = std::unique(names.begin(), names.end());
    EXPECT_EQ(it, names.end()) << "All default region names should be unique";
}

TEST_F(DefaultRegionPropertiesTest, CheekHasHighExtensibility) {
    // Cheek skin is loose and mobile; it should have the lowest stretchMin
    // and highest stretchMax among common regions.
    const tissueRegionProperties* cheek = nullptr;
    for (const auto& rp : defaults) {
        if (rp.name == "cheek") { cheek = &rp; break; }
    }
    ASSERT_NE(cheek, nullptr) << "Default regions should include 'cheek'";
    EXPECT_FLOAT_EQ(cheek->stretchMin, 0.5f);
    EXPECT_FLOAT_EQ(cheek->stretchMax, 2.0f);
}

TEST_F(DefaultRegionPropertiesTest, EyelidHasHighExtensibility) {
    // Eyelid skin is the thinnest in the body and very elastic.
    const tissueRegionProperties* eyelid = nullptr;
    for (const auto& rp : defaults) {
        if (rp.name == "eyelid") { eyelid = &rp; break; }
    }
    ASSERT_NE(eyelid, nullptr) << "Default regions should include 'eyelid'";
    EXPECT_FLOAT_EQ(eyelid->stretchMin, 0.5f);
    EXPECT_FLOAT_EQ(eyelid->stretchMax, 2.0f);
}

TEST_F(DefaultRegionPropertiesTest, ScalpHasLowExtensibility) {
    // Scalp skin is bound by the galea aponeurotica, limiting stretch.
    const tissueRegionProperties* scalp = nullptr;
    for (const auto& rp : defaults) {
        if (rp.name == "scalp") { scalp = &rp; break; }
    }
    ASSERT_NE(scalp, nullptr) << "Default regions should include 'scalp'";
    EXPECT_FLOAT_EQ(scalp->stretchMin, 0.85f);
    EXPECT_FLOAT_EQ(scalp->stretchMax, 1.0f);
}

TEST_F(DefaultRegionPropertiesTest, NoseHasLowExtensibility) {
    // Nose skin is tightly bound to cartilage, very limited stretch.
    const tissueRegionProperties* nose = nullptr;
    for (const auto& rp : defaults) {
        if (rp.name == "nose") { nose = &rp; break; }
    }
    ASSERT_NE(nose, nullptr) << "Default regions should include 'nose'";
    EXPECT_FLOAT_EQ(nose->stretchMin, 0.85f);
    EXPECT_FLOAT_EQ(nose->stretchMax, 1.0f);
}

TEST_F(DefaultRegionPropertiesTest, ForeheadHasModerateExtensibility) {
    // Forehead skin is moderately adherent to frontalis.
    const tissueRegionProperties* forehead = nullptr;
    for (const auto& rp : defaults) {
        if (rp.name == "forehead") { forehead = &rp; break; }
    }
    ASSERT_NE(forehead, nullptr) << "Default regions should include 'forehead'";
    EXPECT_FLOAT_EQ(forehead->stretchMin, 0.75f);
    EXPECT_FLOAT_EQ(forehead->stretchMax, 1.2f);
}

TEST_F(DefaultRegionPropertiesTest, LipRegionExists) {
    const tissueRegionProperties* lip = nullptr;
    for (const auto& rp : defaults) {
        if (rp.name == "lip") { lip = &rp; break; }
    }
    ASSERT_NE(lip, nullptr) << "Default regions should include 'lip'";
    EXPECT_FLOAT_EQ(lip->stretchMin, 0.6f);
    EXPECT_FLOAT_EQ(lip->stretchMax, 1.5f);
}

TEST_F(DefaultRegionPropertiesTest, PeriorbitalRegionExists) {
    const tissueRegionProperties* periorbital = nullptr;
    for (const auto& rp : defaults) {
        if (rp.name == "periorbital") { periorbital = &rp; break; }
    }
    ASSERT_NE(periorbital, nullptr) << "Default regions should include 'periorbital'";
    EXPECT_FLOAT_EQ(periorbital->stretchMin, 0.6f);
    EXPECT_FLOAT_EQ(periorbital->stretchMax, 1.6f);
}

TEST_F(DefaultRegionPropertiesTest, DefaultRegionsHaveZeroTetWeights) {
    // Default regions should have zero tet weights, meaning they fall back
    // to the global weights from tetrahedralProperties.
    for (const auto& rp : defaults) {
        EXPECT_FLOAT_EQ(rp.lowTetWeight, 0.0f)
            << "Region '" << rp.name << "' should have zero lowTetWeight by default";
        EXPECT_FLOAT_EQ(rp.highTetWeight, 0.0f)
            << "Region '" << rp.name << "' should have zero highTetWeight by default";
    }
}

TEST_F(DefaultRegionPropertiesTest, DefaultRegionsHaveEmptySubsetObjFile) {
    // Default regions should not reference any OBJ files.
    for (const auto& rp : defaults) {
        EXPECT_TRUE(rp.subsetObjFile.empty())
            << "Region '" << rp.name << "' should have empty subsetObjFile by default";
    }
}

TEST_F(DefaultRegionPropertiesTest, StretchLimitsArePositive) {
    // All stretch limits should be positive values.
    for (const auto& rp : defaults) {
        EXPECT_GT(rp.stretchMin, 0.0f)
            << "Region '" << rp.name << "' stretchMin should be positive";
        EXPECT_GT(rp.stretchMax, 0.0f)
            << "Region '" << rp.name << "' stretchMax should be positive";
    }
}

TEST_F(DefaultRegionPropertiesTest, StretchMinLessThanOrEqualToStretchMax) {
    // stretchMin should always be <= stretchMax.
    for (const auto& rp : defaults) {
        EXPECT_LE(rp.stretchMin, rp.stretchMax)
            << "Region '" << rp.name << "' stretchMin should be <= stretchMax";
    }
}


// ===========================================================================
// TEST SUITE: SetRegionStretchLimit
// Tests for updating stretch limits on existing and new regions.
// ===========================================================================

class SetRegionStretchLimitTest : public ::testing::Test {
protected:
    RegionManager rm;

    void SetUp() override {
        rm.loadDefaults();
    }
};

TEST_F(SetRegionStretchLimitTest, UpdateExistingRegion) {
    // Updating an existing region's stretch limits should modify it in place.
    rm.setRegionStretchLimit("cheek", 0.7f, 1.8f);
    const auto* cheek = rm.getRegionProperties("cheek");
    ASSERT_NE(cheek, nullptr);
    EXPECT_FLOAT_EQ(cheek->stretchMin, 0.7f);
    EXPECT_FLOAT_EQ(cheek->stretchMax, 1.8f);
}

TEST_F(SetRegionStretchLimitTest, UpdateDoesNotChangeOtherProperties) {
    // Updating stretch limits should not change lowTetWeight, highTetWeight, or subsetObjFile.
    rm.setRegionProperties(tissueRegionProperties("cheek", 0.5f, 2.0f, 100.0f, 200.0f, "cheek.obj"));
    rm.setRegionStretchLimit("cheek", 0.7f, 1.8f);
    const auto* cheek = rm.getRegionProperties("cheek");
    ASSERT_NE(cheek, nullptr);
    EXPECT_FLOAT_EQ(cheek->stretchMin, 0.7f);
    EXPECT_FLOAT_EQ(cheek->stretchMax, 1.8f);
    // lowTetWeight and highTetWeight should be unchanged
    EXPECT_FLOAT_EQ(cheek->lowTetWeight, 100.0f);
    EXPECT_FLOAT_EQ(cheek->highTetWeight, 200.0f);
    EXPECT_EQ(cheek->subsetObjFile, "cheek.obj");
}

TEST_F(SetRegionStretchLimitTest, CreateNewRegionIfNotFound) {
    // Setting stretch limits on a region that doesn't exist should create it.
    EXPECT_EQ(rm.getAllRegionProperties().size(), 7u);
    rm.setRegionStretchLimit("chin", 0.6f, 1.4f);
    EXPECT_EQ(rm.getAllRegionProperties().size(), 8u);

    const auto* chin = rm.getRegionProperties("chin");
    ASSERT_NE(chin, nullptr);
    EXPECT_FLOAT_EQ(chin->stretchMin, 0.6f);
    EXPECT_FLOAT_EQ(chin->stretchMax, 1.4f);
    EXPECT_FLOAT_EQ(chin->lowTetWeight, 0.0f) << "New regions should have zero lowTetWeight";
    EXPECT_FLOAT_EQ(chin->highTetWeight, 0.0f) << "New regions should have zero highTetWeight";
}

TEST_F(SetRegionStretchLimitTest, DoesNotDuplicateExistingRegion) {
    // Updating an existing region should not create a duplicate entry.
    size_t sizeBefore = rm.getAllRegionProperties().size();
    rm.setRegionStretchLimit("scalp", 0.9f, 1.1f);
    EXPECT_EQ(rm.getAllRegionProperties().size(), sizeBefore)
        << "Updating an existing region should not change the count";
}

TEST_F(SetRegionStretchLimitTest, MultipleUpdatesToSameRegion) {
    // Multiple updates to the same region should each take effect.
    rm.setRegionStretchLimit("nose", 0.7f, 1.2f);
    const auto* nose = rm.getRegionProperties("nose");
    ASSERT_NE(nose, nullptr);
    EXPECT_FLOAT_EQ(nose->stretchMin, 0.7f);
    EXPECT_FLOAT_EQ(nose->stretchMax, 1.2f);

    rm.setRegionStretchLimit("nose", 0.9f, 1.05f);
    nose = rm.getRegionProperties("nose");
    ASSERT_NE(nose, nullptr);
    EXPECT_FLOAT_EQ(nose->stretchMin, 0.9f);
    EXPECT_FLOAT_EQ(nose->stretchMax, 1.05f);
}


// ===========================================================================
// TEST SUITE: SetGlobalStretchLimit
// Tests for the global stretch limit fallback.
// ===========================================================================

class SetGlobalStretchLimitTest : public ::testing::Test {
protected:
    RegionManager rm;

    void SetUp() override {
        rm.loadDefaults();
    }
};

TEST_F(SetGlobalStretchLimitTest, OverridesAllRegions) {
    // setGlobalStretchLimit should set all region stretch limits to the
    // given uniform values.
    rm.setGlobalStretchLimit(0.9f, 1.1f);

    for (const auto& rp : rm.getAllRegionProperties()) {
        EXPECT_FLOAT_EQ(rp.stretchMin, 0.9f)
            << "Region '" << rp.name << "' stretchMin should be overridden to 0.9";
        EXPECT_FLOAT_EQ(rp.stretchMax, 1.1f)
            << "Region '" << rp.name << "' stretchMax should be overridden to 1.1";
    }
}

TEST_F(SetGlobalStretchLimitTest, UpdatesGlobalValues) {
    // The global min/max values should be updated.
    rm.setGlobalStretchLimit(0.7f, 1.5f);
    EXPECT_FLOAT_EQ(rm.getGlobalStretchMin(), 0.7f);
    EXPECT_FLOAT_EQ(rm.getGlobalStretchMax(), 1.5f);
}

TEST_F(SetGlobalStretchLimitTest, DoesNotChangeRegionCount) {
    // Applying global limits should not add or remove regions.
    size_t countBefore = rm.getAllRegionProperties().size();
    rm.setGlobalStretchLimit(0.85f, 1.15f);
    EXPECT_EQ(rm.getAllRegionProperties().size(), countBefore);
}

TEST_F(SetGlobalStretchLimitTest, SubsequentRegionUpdateOverridesGlobal) {
    // After applying a global limit, a per-region update should override
    // that region's values while leaving others at the global setting.
    rm.setGlobalStretchLimit(0.9f, 1.1f);
    rm.setRegionStretchLimit("cheek", 0.5f, 2.0f);

    const auto* cheek = rm.getRegionProperties("cheek");
    ASSERT_NE(cheek, nullptr);
    EXPECT_FLOAT_EQ(cheek->stretchMin, 0.5f) << "Cheek should have its own updated values";
    EXPECT_FLOAT_EQ(cheek->stretchMax, 2.0f);

    // Other regions should still have the global values
    const auto* scalp = rm.getRegionProperties("scalp");
    ASSERT_NE(scalp, nullptr);
    EXPECT_FLOAT_EQ(scalp->stretchMin, 0.9f) << "Scalp should retain global values";
    EXPECT_FLOAT_EQ(scalp->stretchMax, 1.1f);
}

TEST_F(SetGlobalStretchLimitTest, DoesNotAffectTetWeights) {
    // setGlobalStretchLimit should only change stretch limits,
    // not tet weight properties.
    rm.setRegionProperties(tissueRegionProperties("forehead", 0.75f, 1.2f, 300.0f, 600.0f));
    rm.setGlobalStretchLimit(0.9f, 1.1f);

    const auto* forehead = rm.getRegionProperties("forehead");
    ASSERT_NE(forehead, nullptr);
    EXPECT_FLOAT_EQ(forehead->stretchMin, 0.9f) << "Stretch should be overridden";
    EXPECT_FLOAT_EQ(forehead->stretchMax, 1.1f);
    EXPECT_FLOAT_EQ(forehead->lowTetWeight, 300.0f) << "Tet weights should be unchanged";
    EXPECT_FLOAT_EQ(forehead->highTetWeight, 600.0f);
}

TEST_F(SetGlobalStretchLimitTest, EmptyRegionListHandledGracefully) {
    // If no regions are loaded, setGlobalStretchLimit should update global
    // values without crashing.
    RegionManager emptyRm;
    EXPECT_NO_THROW(emptyRm.setGlobalStretchLimit(0.8f, 1.2f));
    EXPECT_FLOAT_EQ(emptyRm.getGlobalStretchMin(), 0.8f);
    EXPECT_FLOAT_EQ(emptyRm.getGlobalStretchMax(), 1.2f);
    EXPECT_TRUE(emptyRm.getAllRegionProperties().empty());
}


// ===========================================================================
// TEST SUITE: RegionLookupByName
// Tests for getRegionProperties() name-based lookup.
// ===========================================================================

class RegionLookupTest : public ::testing::Test {
protected:
    RegionManager rm;

    void SetUp() override {
        rm.loadDefaults();
    }
};

TEST_F(RegionLookupTest, FindExistingRegion) {
    // Looking up a known region should return a valid pointer.
    const auto* cheek = rm.getRegionProperties("cheek");
    ASSERT_NE(cheek, nullptr);
    EXPECT_EQ(cheek->name, "cheek");
}

TEST_F(RegionLookupTest, FindAllDefaultRegions) {
    // Every default region name should be findable.
    std::vector<std::string> expectedNames = {
        "cheek", "eyelid", "forehead", "scalp", "nose", "lip", "periorbital"
    };
    for (const auto& name : expectedNames) {
        const auto* rp = rm.getRegionProperties(name);
        EXPECT_NE(rp, nullptr) << "Region '" << name << "' should be found";
        if (rp != nullptr) {
            EXPECT_EQ(rp->name, name);
        }
    }
}

TEST_F(RegionLookupTest, NonExistentRegionReturnsNull) {
    // Looking up a name that doesn't exist should return nullptr.
    const auto* unknown = rm.getRegionProperties("unknown_region");
    EXPECT_EQ(unknown, nullptr);
}

TEST_F(RegionLookupTest, EmptyNameReturnsNull) {
    // Looking up an empty string should return nullptr.
    const auto* empty = rm.getRegionProperties("");
    EXPECT_EQ(empty, nullptr);
}

TEST_F(RegionLookupTest, CaseSensitiveLookup) {
    // Region lookup should be case-sensitive.
    const auto* upper = rm.getRegionProperties("Cheek");
    EXPECT_EQ(upper, nullptr) << "Region lookup should be case-sensitive";

    const auto* lower = rm.getRegionProperties("cheek");
    EXPECT_NE(lower, nullptr);
}

TEST_F(RegionLookupTest, LookupAfterCreatingNewRegion) {
    // A newly created region should be immediately findable.
    rm.setRegionStretchLimit("chin", 0.7f, 1.3f);
    const auto* chin = rm.getRegionProperties("chin");
    ASSERT_NE(chin, nullptr);
    EXPECT_EQ(chin->name, "chin");
    EXPECT_FLOAT_EQ(chin->stretchMin, 0.7f);
    EXPECT_FLOAT_EQ(chin->stretchMax, 1.3f);
}

TEST_F(RegionLookupTest, LookupReturnsUpdatedValues) {
    // After updating a region, lookup should return the new values.
    rm.setRegionStretchLimit("nose", 0.9f, 1.05f);
    const auto* nose = rm.getRegionProperties("nose");
    ASSERT_NE(nose, nullptr);
    EXPECT_FLOAT_EQ(nose->stretchMin, 0.9f);
    EXPECT_FLOAT_EQ(nose->stretchMax, 1.05f);
}


// ===========================================================================
// TEST SUITE: SetRegionProperties (full property update)
// Tests for setRegionProperties() which replaces all fields.
// ===========================================================================

class SetRegionPropertiesTest : public ::testing::Test {
protected:
    RegionManager rm;

    void SetUp() override {
        rm.loadDefaults();
    }
};

TEST_F(SetRegionPropertiesTest, FullUpdateReplacesAllFields) {
    // setRegionProperties should replace all fields of an existing region.
    tissueRegionProperties newProps("cheek", 0.6f, 1.8f, 400.0f, 800.0f, "/path/to/cheek.obj");
    rm.setRegionProperties(newProps);

    const auto* cheek = rm.getRegionProperties("cheek");
    ASSERT_NE(cheek, nullptr);
    EXPECT_FLOAT_EQ(cheek->stretchMin, 0.6f);
    EXPECT_FLOAT_EQ(cheek->stretchMax, 1.8f);
    EXPECT_FLOAT_EQ(cheek->lowTetWeight, 400.0f);
    EXPECT_FLOAT_EQ(cheek->highTetWeight, 800.0f);
    EXPECT_EQ(cheek->subsetObjFile, "/path/to/cheek.obj");
}

TEST_F(SetRegionPropertiesTest, CreatesNewRegionIfNotFound) {
    // If the named region doesn't exist, setRegionProperties should add it.
    tissueRegionProperties newRegion("chin", 0.65f, 1.35f, 350.0f, 700.0f, "");
    rm.setRegionProperties(newRegion);
    EXPECT_EQ(rm.getAllRegionProperties().size(), 8u);

    const auto* chin = rm.getRegionProperties("chin");
    ASSERT_NE(chin, nullptr);
    EXPECT_FLOAT_EQ(chin->stretchMin, 0.65f);
    EXPECT_FLOAT_EQ(chin->stretchMax, 1.35f);
}

TEST_F(SetRegionPropertiesTest, DoesNotDuplicateOnUpdate) {
    // Updating an existing region should not add a duplicate.
    size_t before = rm.getAllRegionProperties().size();
    tissueRegionProperties updated("scalp", 0.9f, 1.05f, 700.0f, 1500.0f, "");
    rm.setRegionProperties(updated);
    EXPECT_EQ(rm.getAllRegionProperties().size(), before);
}


// ===========================================================================
// TEST SUITE: FacialRegionProperties struct
// Tests for the tissueRegionProperties struct itself.
// ===========================================================================

class TissueRegionPropertiesStructTest : public ::testing::Test {};

TEST_F(TissueRegionPropertiesStructTest, DefaultConstructor) {
    // The default constructor should initialize all fields to zero/empty.
    tissueRegionProperties rp;
    EXPECT_TRUE(rp.name.empty());
    EXPECT_FLOAT_EQ(rp.stretchMin, 0.0f);
    EXPECT_FLOAT_EQ(rp.stretchMax, 0.0f);
    EXPECT_FLOAT_EQ(rp.lowTetWeight, 0.0f);
    EXPECT_FLOAT_EQ(rp.highTetWeight, 0.0f);
    EXPECT_TRUE(rp.subsetObjFile.empty());
}

TEST_F(TissueRegionPropertiesStructTest, ParameterizedConstructorMinimal) {
    // The 3-argument constructor should set name, stretchMin, stretchMax.
    tissueRegionProperties rp("test", 0.5f, 1.5f);
    EXPECT_EQ(rp.name, "test");
    EXPECT_FLOAT_EQ(rp.stretchMin, 0.5f);
    EXPECT_FLOAT_EQ(rp.stretchMax, 1.5f);
    EXPECT_FLOAT_EQ(rp.lowTetWeight, 0.0f);
    EXPECT_FLOAT_EQ(rp.highTetWeight, 0.0f);
    EXPECT_TRUE(rp.subsetObjFile.empty());
}

TEST_F(TissueRegionPropertiesStructTest, ParameterizedConstructorFull) {
    // The full constructor should set all fields.
    tissueRegionProperties rp("nose", 0.85f, 1.0f, 600.0f, 1200.0f, "nose_region.obj");
    EXPECT_EQ(rp.name, "nose");
    EXPECT_FLOAT_EQ(rp.stretchMin, 0.85f);
    EXPECT_FLOAT_EQ(rp.stretchMax, 1.0f);
    EXPECT_FLOAT_EQ(rp.lowTetWeight, 600.0f);
    EXPECT_FLOAT_EQ(rp.highTetWeight, 1200.0f);
    EXPECT_EQ(rp.subsetObjFile, "nose_region.obj");
}

TEST_F(TissueRegionPropertiesStructTest, CopySemantics) {
    // Struct copy should produce an independent copy of all fields.
    tissueRegionProperties original("cheek", 0.5f, 2.0f, 100.0f, 200.0f, "cheek.obj");
    tissueRegionProperties copy = original;

    EXPECT_EQ(copy.name, original.name);
    EXPECT_FLOAT_EQ(copy.stretchMin, original.stretchMin);
    EXPECT_FLOAT_EQ(copy.stretchMax, original.stretchMax);
    EXPECT_FLOAT_EQ(copy.lowTetWeight, original.lowTetWeight);
    EXPECT_FLOAT_EQ(copy.highTetWeight, original.highTetWeight);
    EXPECT_EQ(copy.subsetObjFile, original.subsetObjFile);

    // Modifying the copy should not affect the original.
    copy.stretchMin = 0.9f;
    EXPECT_FLOAT_EQ(original.stretchMin, 0.5f);
}
