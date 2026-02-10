// Proposed interface for pdTetPhysics library:
//  Wang, Tao, Cutting, Sifakis
// Date: 1/30/2020

#pragma once

#include <vector>
#include <array>
#include <unordered_map>
#include "PDTetSolver.h"
#include "Utilities.h"


/** @brief Projective dynamics physics solver wrapper for BCC tetrahedral simulation.
 *
 * Provides the high-level interface to the PDTetSolver, managing hooks, sutures,
 * collision objects, fixed vertex constraints, and per-tet material properties.
 * Used by bccTetScene to drive the deformable tissue physics each frame.
 */
class pdTetPhysics {
	// a very unsafe wrapper class
private:
	using T = float;
	static constexpr int d = 3;
	PDTetSolver<T, d> m_solver;
	T m_hookWeight{ 0 };
	T m_sutureWeight{ 0 };
	T m_fixedWeight{ 0 };
	T m_peripheralWeight{ 0 };
	T m_tJunctionWeight{ 0 };

	T m_stressLimit{ 1 };

	std::vector<int> fixedTetConstraints;

public:
	/// @brief Add a rigid collision level-set object from an OBJ file path.
	inline void addCollisionObject(const std::string& collisionObjPath) {
		m_solver.addLevelSet(collisionObjPath);
	}

	/// @brief Register tets that participate in soft (self) collision detection.
	void addSoftCollisionTets(const std::vector<int> &tets) {
		m_solver.addSelfCollisionElements(&tets[0], tets.size());
	}

	/** @brief Add a fixed collision set with a level-set surface and proxy tets/weights.
	 *
	 * Loads the level-set once on first call; subsequent calls only update proxy data.
	 */
	void addFixedCollisionSet(const std::string &levelSetFile, const std::vector<int> &tets, const std::vector<std::array<float, 3> > &weights) {
		if (!m_levelsetInited)
			addCollisionObject(levelSetFile);
		inputCollisionProxies(tets, weights);
			// called after every topological change as tets and weights will change.  Check to see if levelSetFile has already been loaded.  This only needs to be done on initial load and not repeated.
	}

	/// @brief Update the current frame's soft collision suture pairs between top and bottom surfaces.
	void currentSoftCollisionPairs(const std::vector<int> &topTets, const std::vector<std::array<float, 3> > &topBarys,
		const std::vector<int> &bottomTets, const std::vector<std::array<float, 3> > &bottomBarys, const std::vector<std::array<float, 3> > &collisionNormals) {
		assert(topTets.size() == topBarys.size() && topTets.size() == bottomTets.size() && topTets.size() == bottomBarys.size() && topTets.size() == collisionNormals.size());

		if (topTets.size())
			m_solver.updateCollisionSutures(topTets.size(), topTets.data(), bottomTets.data(), topBarys[0].data(), bottomBarys[0].data(), collisionNormals[0].data());
	}

	/// @brief Remove all soft collision sutures for the current frame.
	inline void clearSoftCollisions() {
		m_solver.clearCollisionSutures();
	}

	/** @brief Set global tetrahedral material properties (can only be called once).
	 *  @param lowTetWeight   Stiffness weight for low-resolution tets.
	 *  @param highTetWeight  Stiffness weight for high-resolution tets.
	 *  @param TJunctionWeight  Weight for T-junction internode constraints.
	 *  @param strainMin  Global minimum strain limit (compression).
	 *  @param strainMax  Global maximum strain limit (extension).
	 *  @param collisionWeight  Weight for fixed collision constraints.
	 *  @param selfCollisionWeight  Weight for self-collision constraints.
	 *  @param fixedWeight  Weight for Dirichlet (fixed vertex) constraints.
	 *  @param peripheralWeight  Weight for peripheral boundary constraints.
	 */
	inline void setTetProperties(const float lowTetWeight, const float highTetWeight, const float TJunctionWeight, const float strainMin, const float strainMax, const float collisionWeight, const float selfCollisionWeight, const float fixedWeight, const float peripheralWeight) {
		// guard against reset tetProperties
		if (m_tetPropsSet)
			throw std::logic_error("tet properties can only be set once");
		else
			m_tetPropsSet = true;
		m_fixedWeight = fixedWeight;
		m_peripheralWeight = peripheralWeight;
		m_tJunctionWeight = TJunctionWeight;
		m_solver.setParameters(highTetWeight / 2, lowTetWeight / highTetWeight, strainMin, strainMax, collisionWeight, selfCollisionWeight);
	}

	/** @brief Assign per-subset tet properties (stiffness and strain limits) to a group of tets.
	 *  @param tets  Indices of tets belonging to this subset (e.g. cartilage, specific tissue region).
	 */
	inline void tetSubset(const float lowTetWeight, const float highTetWeight, const float strainMin, const float strainMax, const std::vector<int>& tets) {
		m_solver.addSubset(highTetWeight / 2, lowTetWeight / highTetWeight, strainMin, strainMax, tets);

		// QISI - write me.  First 4 arguments are the tet properties of this subset of tets.  Last argument contains the indices of the tets these
		// properties should be assigned to.  This will be called after every topo change.  Currently there will be only one of these for cartilage.
		// In the there may be several of these for different tissue type within the body.
		std::cout << "calling tetSubset with set size : "<<tets.size() << std::endl;
	}

	/// @brief Return true if the solver has been fully initialized and is ready to solve.
	inline bool solverInitialized() { return m_solverInited; }

	/** @brief Create the BCC tet deformer from tet index data at a single resolution.
	 *  @param tetIndices  Vector of tet node index quadruples.
	 *  @param tetScale    Half-width of the smallest tet cell.
	 *  @return Pointer to the solver's position array (3 floats per node).
	 */
	inline std::array<float, 3>* createBccTetStructure(const std::vector< std::array<int, 4> > &tetIndices, float tetScale) {
		m_solver.initializeDeformer(reinterpret_cast<const int(*)[4]>(&tetIndices[0][0]), tetIndices.size(), tetScale * 2);
		m_deformerInited = true;
		m_solverInited = false;
		fixedTetConstraints.clear();
		return reinterpret_cast<std::array<T, d>(*)>(m_solver.getPositionPtr());
	}

	/** @brief Create the BCC tet deformer with multi-resolution tet sizes.
	 *  @param tetIndices       Vector of tet node index quadruples.
	 *  @param tetSizeMultiples  Size multiplier per tet (1 = smallest, 2 = 2x, etc.).
	 *  @param tetScale         Half-width of the smallest tet cell.
	 *  @return Pointer to the solver's position array (3 floats per node).
	 */
	inline std::array<float, 3>* createBccTetStructure_multires(const std::vector< std::array<int, 4> >& tetIndices, const std::vector<uint8_t>& tetSizeMultiples, float tetScale) {
		m_solver.initializeDeformer_multires(reinterpret_cast<const int(*)[4]>(&tetIndices[0][0]), reinterpret_cast<const uint8_t*>(&tetSizeMultiples[0]), tetIndices.size(), tetScale * 2);
		m_deformerInited = true;
		m_solverInited = false;
		fixedTetConstraints.clear();
		return reinterpret_cast<std::array<T, d>(*)>(m_solver.getPositionPtr());
	}

	/** @brief Add T-junction internode constraints between multi-resolution tet faces.
	 *  @param subNodes          Nodes on the smaller tet that lie on a larger tet's face.
	 *  @param faceNodes         For each subNode, the larger-face nodes that constrain it.
	 *  @param faceBarycentrics  Barycentric weights corresponding to each faceNode set.
	 */
	void addInterNodeConstraints(const std::vector<int>& subNodes, const std::vector<std::vector<int> >& faceNodes, const std::vector<std::vector<float> >& faceBarycentrics) {
		int sns = subNodes.size();
		assert(sns == faceNodes.size() && sns == faceBarycentrics.size());
		for (int i = 0; i < sns; i++) {
			if (faceNodes[i].size() > 3) {
				// std::cout << i << "th internode needs " << faceNodes[i].size() << " macro nodes" << std::endl;
				m_solver.addInterNodeConstraint(subNodes[i], faceNodes[i].size(), &faceNodes[i][0], &faceBarycentrics[i][0], 0);  // QISI - currently not processing these?
			} else {
				int l = faceNodes[i].size() < 3 ? faceNodes[i].size() : 3;
				int fN[3]{}; for (int v = 0; v < l; ++v) fN[v] = faceNodes[i][v];
				float bC[3]{}; for (int v = 0; v < l; ++v) bC[v] = faceBarycentrics[i][v];
				int handle = m_solver.addInterNodeConstraint(subNodes[i], fN, bC, m_tJunctionWeight);
			}
		}
	}

	/** @brief Set Dirichlet (fixed) and peripheral boundary vertex constraints.
	 *
	 * Replaces any existing fixed/peripheral constraints. May be called after topology
	 * changes or periosteal undermining without requiring a full tet rebuild.
	 */
	inline void setFixedVertices(const std::vector<int> &fixedTets, const std::vector<std::array<float, 3> > &fixedWeights, const std::vector<std::array<float, 3> > &fixedPositions,
		const std::vector<int> &peripheralTets, const std::vector<std::array<float, 3> > &peripheralWeights, const std::vector<std::array<float, 3> > &peripheralPositions) {
		if (!m_deformerInited)
			throw std::logic_error("need to init tet topology before setFixedNodes");
		const T weight[d] = { 0,0,0 };

		// QISI - I see your m_grid_deformer handles tet constraints for hooks and fixed vertices.  Will hooks always be the last?  This is somewhat ugly.  Please advise.
		if (m_solver.numberOfTetConstraints() >= fixedTetConstraints.size()) {
			for (auto& tc : fixedTetConstraints)
				m_solver.deleteConstraint(tc);
		}
		fixedTetConstraints.clear();

		assert(fixedTets.size() == fixedWeights.size() && fixedWeights.size() == fixedPositions.size());
		assert(peripheralTets.size() == peripheralWeights.size() && peripheralWeights.size() == peripheralPositions.size());
		fixedTetConstraints.reserve(fixedTets.size() + peripheralTets.size());
		int fts = fixedTets.size();
		for (int i = 0; i < fts; i++) {
			int handle = m_solver.addConstraint(reinterpret_cast<const int(&)[4]>(m_solver.getTetIndices(fixedTets[i])), reinterpret_cast<const T(&)[3]>(fixedWeights[i]), reinterpret_cast<const T(&)[3]>(fixedPositions[i]), m_fixedWeight); // change weight
			fixedTetConstraints.push_back(handle);
		}
		for (int i = 0; i < peripheralTets.size(); i++) {
			int handle = m_solver.addConstraint(reinterpret_cast<const int(&)[4]>(m_solver.getTetIndices(peripheralTets[i])), reinterpret_cast<const T(&)[3]>(peripheralWeights[i]), reinterpret_cast<const T(&)[3]>(peripheralPositions[i]), m_peripheralWeight); // change weight
			fixedTetConstraints.push_back(handle);
		}
	}

	/** @brief Add a hook constraint at a barycentric location within a tet.
	 *  @param tet               Tet index containing the hook point.
	 *  @param barycentricWeight Barycentric coordinates within the tet.
	 *  @param hookPosition      Target spatial position for the hook.
	 *  @param strong            If true, apply greatly increased hook stiffness.
	 *  @return Constraint handle for later moveHook() or deleteHook() calls.
	 */
	inline int addHook(const int tet, const std::array<float, 3> &barycentricWeight, const std::array<float, 3> &hookPosition, bool strong = false) {
		if (!m_deformerInited)
			throw std::logic_error("need to init tet topology before addHook");
		int number;
		if(strong)
			number = m_solver.addConstraint(tet, reinterpret_cast<const T(&)[d]>(barycentricWeight), reinterpret_cast<const T(&)[d]>(hookPosition), m_hookWeight*200.0f, m_stressLimit*2000.0f);
		else
			number = m_solver.addConstraint(tet, reinterpret_cast<const T(&)[d]>(barycentricWeight), reinterpret_cast<const T(&)[d]>(hookPosition), m_hookWeight, m_stressLimit);
//		initializePhysics();  // don't do this here.  Do in calling routine due to group initilization.
		return number;
	}

	/// @brief Move an existing hook constraint to a new spatial position.
	inline void moveHook(const int hookHandle, const std::array<float, 3> &newPosition) {
		if (!m_deformerInited)
			throw std::logic_error("need to init tet topology before moveHook");
		m_solver.moveConstraint(hookHandle, reinterpret_cast<const T(&)[d]>(newPosition));
	}

	/// @brief Delete a hook constraint by its handle.
	inline void deleteHook(const int hookHandle) {
		if (!m_deformerInited)
			throw std::logic_error("need to init tet topology before deleteHook");
		m_solver.deleteConstraint(hookHandle);
	}

	/// @brief Set the stiffness weights for hooks and sutures, and an optional stress limit.
	inline void setHookSutureWeights(const float hookWeight, const float sutureWeight, const float stressLimit = FLT_MAX) {
		m_hookWeight = hookWeight;
		m_sutureWeight = sutureWeight;
		m_stressLimit = stressLimit;
	}

	/** @brief Add a suture constraint connecting two barycentric points in two tets.
	 *  @return Constraint handle for later deleteSuture() calls.
	 */
	inline int addSuture(const int(&tets)[2], const std::array<float, 3>(&barycentricWeights)[2]) {
		// unlike hooks doesn't call initializePhysics() here due to suture group entry.
		// Must call initializePhysics() in calling routine handling individual versus group entry.
		if (!m_deformerInited)
			throw std::logic_error("need to init tet topology before addSuture");
		// m_solverInited = false;
		return m_solver.addSuture(tets, reinterpret_cast<const T(&)[2][d]>(barycentricWeights[0]), sqrt(m_sutureWeight));
	}

	/// @brief Delete a suture constraint by its handle.
	inline void deleteSuture(const int sutureHandle) {
		if (!m_deformerInited)
			throw std::logic_error("need to init tet topology before deleteSuture");
		m_solver.deleteSuture(sutureHandle);
	}

	/** @brief Initialize or re-initialize the physics solver after constraint changes.
	 *
	 * On first call, builds the system matrix (ATA) and performs LDLT factorization.
	 * On subsequent calls, re-factorizes to incorporate added/removed constraints.
	 */
	inline void initializePhysics() {
		if (m_solverInited) {
			reInitializePhysics();
		}
		else {
			// the tetProperties need to be set before calling this
			if (!m_deformerInited)
				throw std::logic_error("need to init tet topology before init solver");
			// guard against init with no tet properties
			if (!m_tetPropsSet)
				throw std::logic_error("need to set tetProperties before initializePhysics");
			initializeCollisionObject(0.03f);
			promoteAllSutures();
			m_solver.initializeSolver();
			m_solverInited = true;
		}
	}
	// Adding and deleting hooks can have an initializePhysics() call at the end of them as they are always unique. This should not be done with sutures since often a whole line of sutures
	// will be added after which only a single initializePhysics() call is necessary.
	private:
	inline void reInitializePhysics() {
		if (!m_solverInited)
			throw std::logic_error("need to init solver before reinit");
		m_solver.reInitializeSolver();
	}
	public:

	/// @brief Set collision proxy points (tet + barycentric weight) for level-set collision.
	inline void inputCollisionProxies(const std::vector<int> &tets, const std::vector<std::array<float, 3> > &weights) {
		if (!m_deformerInited)
			throw std::logic_error("need to init tet topology before add proxies");
		m_solver.addCollisionProxies(&tets[0], reinterpret_cast<const T(*)[d]>(&weights[0]), tets.size());
	}

	/// @brief Run one iteration of the projective dynamics solver (least-squares solve + collisions).
	inline void solve() {
		if (!m_solverInited)
			throw std::logic_error("need to init solver before solve");
		m_solver.solve();
	}

	pdTetPhysics() : m_tetPropsSet(false), m_solverInited(false), m_deformerInited(false), m_levelsetInited(false) {}

	~pdTetPhysics() {
		m_solver.releaseSolver();
		m_solver.releaseDeformer();
	}

	/// @brief Promote all temporary sutures to permanent constraints. Requires re-initialization.
	inline void promoteAllSutures() { m_solver.premoteSutures(); m_solverInited = false;}

	/// @brief Initialize the level-set collision object at the given grid resolution.
	inline void initializeCollisionObject(const T levelSetDx) { if (!m_levelsetInited) { m_solver.initializeLevelSet(levelSetDx); m_levelsetInited = true; } }

private:
	// static variables as properties

	// cannot reinit if initted
	bool m_deformerInited;
	bool m_solverInited; // only init if deformer inited, only numfact if inited

	bool m_tetPropsSet;
	bool m_levelsetInited;
};
